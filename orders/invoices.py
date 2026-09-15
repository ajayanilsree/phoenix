from decimal import Decimal, ROUND_HALF_UP
import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from accounts.decorators import user_role
from accounts.models import UserProfile
from .models import Invoice, InvoiceItem, Order, SequenceCounter

MONEY = Decimal("0.01")
UNIT_LABELS = {
    "piece": "NOS",
    "box": "BOX",
    "sheet": "SHEET",
    "panel": "PANEL",
    "board": "BOARD",
    "set": "SET",
    "running_foot": "RFT",
    "square_foot": "SQFT",
}
STATE_CODES = {"kerala": "32"}
logger = logging.getLogger(__name__)


class InvoiceGenerationError(Exception):
    pass


def money(value):
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def address_text(address):
    if not address:
        return ""
    lines = [address.line1]
    if address.line2:
        lines.append(address.line2)
    locality = ", ".join(part for part in (address.city, address.district) if part)
    if locality:
        lines.append(locality)
    region = " - ".join(part for part in (address.state, address.postal_code) if part)
    if region:
        lines.append(region)
    if address.country:
        lines.append(address.country)
    return "\n".join(lines)


def amount_in_words(value):
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def under_thousand(number):
        result = []
        if number >= 100:
            result.extend([ones[number // 100], "Hundred"])
            number %= 100
        if number >= 20:
            result.append(tens[number // 10])
            number %= 10
        if number:
            result.append(ones[number])
        return " ".join(result)

    number = int(money(value))
    if number == 0:
        return "Rupees Zero Only"
    parts = []
    crore, number = divmod(number, 10_000_000)
    lakh, number = divmod(number, 100_000)
    thousand, number = divmod(number, 1_000)
    if crore:
        parts.append(f"{under_thousand(crore)} Crore")
    if lakh:
        parts.append(f"{under_thousand(lakh)} Lakh")
    if thousand:
        parts.append(f"{under_thousand(thousand)} Thousand")
    if number:
        parts.append(under_thousand(number))
    return f"Rupees {' '.join(parts)} Only"


def next_sequence(name):
    # Recover counters from already-issued documents. This matters when a
    # production database was migrated after invoices already existed, or a
    # counter row was removed manually.
    defaults = {"next_value": 1}
    prefix = {"invoice_b2c": "PHXINTB2C", "invoice_b2b": "PHXINTB2B"}.get(name)
    if prefix:
        latest = Invoice.objects.filter(invoice_number__startswith=prefix).order_by("-invoice_number").values_list("invoice_number", flat=True).first()
        if latest:
            try:
                defaults["next_value"] = int(latest[len(prefix):]) + 1
            except (TypeError, ValueError):
                logger.warning("Ignoring malformed invoice number while recovering %s: %s", name, latest)
    counter, created = SequenceCounter.objects.select_for_update().get_or_create(name=name, defaults=defaults)
    if not created and prefix:
        latest = Invoice.objects.filter(invoice_number__startswith=prefix).order_by("-invoice_number").values_list("invoice_number", flat=True).first()
        if latest:
            try:
                counter.next_value = max(counter.next_value, int(latest[len(prefix):]) + 1)
            except (TypeError, ValueError):
                logger.warning("Ignoring malformed invoice number while checking %s: %s", name, latest)
    number = counter.next_value
    counter.next_value = number + 1
    counter.save(update_fields=["next_value"])
    return number


def invoice_company_details():
    return {
        "company_name": getattr(settings, "INVOICE_COMPANY_NAME", "PHOENIX INTERIOR HUB"),
        "company_address": getattr(settings, "INVOICE_COMPANY_ADDRESS", ""),
        "company_email": getattr(settings, "INVOICE_COMPANY_EMAIL", "phoenixinteriorhub@gmail.com"),
        "company_mobile": getattr(settings, "INVOICE_COMPANY_MOBILE", "+91 7306430531"),
        "company_gstin": getattr(settings, "INVOICE_COMPANY_GSTIN", ""),
        "company_state": getattr(settings, "INVOICE_COMPANY_STATE", "Kerala"),
    }


def tax_for_line(gross, rate, interstate=False):
    gross = money(gross)
    rate = Decimal(rate or 0)
    if not rate:
        return gross, Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    if getattr(settings, "INVOICE_PRICES_INCLUDE_GST", True):
        taxable = money(gross / (Decimal("1") + rate / Decimal("100")))
    else:
        taxable = gross
    total_gst = money(taxable * rate / Decimal("100"))
    cgst = money(total_gst / Decimal("2"))
    return taxable, cgst, money(total_gst - cgst), Decimal("0.00")


def store_invoice_pdf(invoice):
    """Render and persist an invoice PDF through Django's configured media storage."""
    from .pdf import render_invoice_pdf

    logger.info("INVOICE DEBUG 06 render PDF | order=%s", invoice.order.order_number)
    try:
        pdf_bytes = render_invoice_pdf(invoice)
    except Exception as error:
        logger.exception("Invoice PDF generation failed for order %s", invoice.order.order_number)
        raise InvoiceGenerationError("Invoice PDF could not be generated. Order status was not changed.") from error
    logger.info("INVOICE DEBUG PDF BYTES LENGTH: %s | order=%s", len(pdf_bytes), invoice.order.order_number)
    logger.info("INVOICE DEBUG 07 save PDF | order=%s", invoice.order.order_number)
    try:
        invoice.pdf_file.save(f"{invoice.invoice_number}.pdf", ContentFile(pdf_bytes), save=False)
        invoice.save(update_fields=["pdf_file"])
    except Exception as error:
        logger.exception("Invoice PDF storage failed for order %s", invoice.order.order_number)
        if invoice.pdf_file:
            try:
                invoice.pdf_file.delete(save=False)
            except Exception:
                logger.exception("Invoice PDF cleanup failed for order %s", invoice.order.order_number)
        raise InvoiceGenerationError("Invoice PDF could not be stored. Order status was not changed.") from error


def generate_invoice(order, generated_by, from_address):
    from_address = (from_address or "").strip()
    with transaction.atomic():
        logger.info("INVOICE DEBUG 01 payment validation | order=%s", order.order_number)
        # PostgreSQL cannot apply FOR UPDATE to nullable outer-joined address
        # relations. Lock only the order row; related snapshots remain read-only.
        order = Order.objects.select_for_update(of=("self",)).select_related("customer", "billing_address", "shipping_address").get(pk=order.pk)
        existing = Invoice.objects.filter(order=order).first()
        if existing:
            logger.info("INVOICE DEBUG existing invoice | order=%s invoice=%s pdf=%s", order.order_number, existing.invoice_number, bool(existing.pdf_file.name))
            if not existing.pdf_file:
                store_invoice_pdf(existing)
            logger.info("INVOICE DEBUG 09 set packed | order=%s", order.order_number)
            order.status = Order.PACKED
            order.save(update_fields=["status", "updated_at"])
            return existing
        if order.payment_status != "paid":
            raise InvoiceGenerationError("Invoice can only be generated after payment is confirmed.")
        if not from_address:
            raise InvoiceGenerationError("Please enter the invoice From Address.")
        if not order.billing_address and not order.shipping_address:
            raise InvoiceGenerationError("Invoice cannot be generated because the billing or delivery address is missing.")
        items = list(order.items.select_related("product", "variant").all())
        if not items:
            raise InvoiceGenerationError("Invoice cannot be generated because the order has no products.")
        logger.info("INVOICE DEBUG 02 invoice sequence | order=%s", order.order_number)
        details = invoice_company_details()
        billing = order.billing_address
        shipping = order.shipping_address or order.billing_address
        invoice_type = Invoice.B2B if (billing and billing.gstin) or user_role(order.customer) == UserProfile.AGENT else Invoice.B2C
        prefix = "PHXINTB2B" if invoice_type == Invoice.B2B else "PHXINTB2C"
        invoice_number = f"{prefix}{next_sequence('invoice_b2b' if invoice_type == Invoice.B2B else 'invoice_b2c'):06d}"
        invoice = Invoice.objects.create(
            order=order,
            invoice_number=invoice_number,
            invoice_type=invoice_type,
            invoice_date=timezone.now(),
            company_name=details["company_name"],
            company_address=details["company_address"],
            company_email=details["company_email"],
            company_mobile=details["company_mobile"],
            company_gstin=details["company_gstin"],
            from_address=from_address,
            billing_name=billing.full_name if billing else "",
            billing_address=address_text(billing),
            billing_phone=billing.phone if billing else "",
            billing_gstin=billing.gstin if billing else "",
            shipping_name=shipping.full_name if shipping else "",
            shipping_address=address_text(shipping),
            shipping_phone=shipping.phone if shipping else "",
            shipping_state=shipping.state if shipping else "",
            shipping_state_code=STATE_CODES.get(shipping.state.casefold(), "") if shipping else "",
            shipping_gstin=shipping.gstin if shipping else "",
            grand_total=money(order.grand_total),
            generated_by=generated_by,
        )
        logger.info("INVOICE DEBUG 03 invoice object | order=%s invoice=%s", order.order_number, invoice.invoice_number)
        taxable_total = cgst_total = sgst_total = igst_total = Decimal("0.00")
        logger.info("INVOICE DEBUG 04 invoice items | order=%s count=%s", order.order_number, len(items))
        for line_number, item in enumerate(items, start=1):
            source = item.variant or item.product
            source_rate = getattr(source, "gst_rate", 0)
            raw_rate = item.gst_rate_snapshot if item.gst_rate_snapshot not in (None, 0, Decimal("0.00")) else source_rate
            try:
                rate = Decimal(str(raw_rate or 0))
            except (TypeError, ValueError, ArithmeticError) as error:
                raise InvoiceGenerationError(f"Invoice cannot be generated because GST Rate is invalid for {item.product_name or 'this product'}.") from error
            if rate < 0 or rate > 100:
                raise InvoiceGenerationError(f"Invoice cannot be generated because GST Rate is invalid for {item.product_name or 'this product'}.")
            description = item.product_name or item.selected_variant or getattr(source, "name", "Product")
            hsn_code = item.hsn_code or getattr(source, "hsn_code", "")
            unit_type = item.unit_type or getattr(source, "unit_type", "piece")
            if not item.quantity or item.quantity < 1:
                raise InvoiceGenerationError(f"Invoice cannot be generated because quantity is invalid for {description}.")
            taxable, cgst, sgst, igst = tax_for_line(item.line_total, rate)
            logger.info("INVOICE DEBUG 05 tax calculation | order=%s line=%s", order.order_number, line_number)
            taxable_total += taxable
            cgst_total += cgst
            sgst_total += sgst
            igst_total += igst
            InvoiceItem.objects.create(
                invoice=invoice,
                line_number=line_number,
                description=description,
                hsn_code=hsn_code,
                gst_rate=rate,
                quantity=item.quantity,
                unit=UNIT_LABELS.get(unit_type, unit_type.upper()),
                taxable_unit_rate=money(taxable / item.quantity),
                taxable_amount=taxable,
                cgst_amount=cgst,
                sgst_amount=sgst,
                igst_amount=igst,
                line_total=money(item.line_total),
            )
        invoice.taxable_total = money(taxable_total)
        invoice.cgst_total = money(cgst_total)
        invoice.sgst_total = money(sgst_total)
        invoice.igst_total = money(igst_total)
        invoice.wallet_discount = money(order.wallet_discount_amount)
        invoice.round_off = money(invoice.grand_total - (invoice.taxable_total + invoice.cgst_total + invoice.sgst_total - invoice.wallet_discount))
        invoice.amount_in_words = amount_in_words(invoice.grand_total)
        logger.info("INVOICE DEBUG 08 save invoice | order=%s invoice=%s", order.order_number, invoice.invoice_number)
        invoice.save(update_fields=["taxable_total", "cgst_total", "sgst_total", "igst_total", "wallet_discount", "round_off", "amount_in_words"])
        store_invoice_pdf(invoice)
        logger.info("INVOICE DEBUG 09 set packed | order=%s", order.order_number)
        order.invoice_from_address = from_address
        order.status = Order.PACKED
        order.save(update_fields=["invoice_from_address", "status", "updated_at"])
        return invoice
