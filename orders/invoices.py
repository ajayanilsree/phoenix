from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
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
    counter, _ = SequenceCounter.objects.select_for_update().get_or_create(name=name, defaults={"next_value": 1})
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


def generate_invoice(order, generated_by, from_address):
    from_address = (from_address or "").strip()
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("customer", "billing_address", "shipping_address").get(pk=order.pk)
        existing = Invoice.objects.filter(order=order).first()
        if existing:
            order.status = Order.PACKED
            order.save(update_fields=["status", "updated_at"])
            return existing
        if order.payment_status != "paid":
            raise InvoiceGenerationError("Invoice can only be generated after payment is confirmed.")
        if not from_address:
            raise InvoiceGenerationError("Please enter the invoice From Address.")
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
        taxable_total = cgst_total = sgst_total = igst_total = Decimal("0.00")
        for line_number, item in enumerate(order.items.all(), start=1):
            rate = Decimal(item.gst_rate_snapshot or 0)
            taxable, cgst, sgst, igst = tax_for_line(item.line_total, rate)
            taxable_total += taxable
            cgst_total += cgst
            sgst_total += sgst
            igst_total += igst
            InvoiceItem.objects.create(
                invoice=invoice,
                line_number=line_number,
                description=item.product_name,
                hsn_code=item.hsn_code,
                gst_rate=rate,
                quantity=item.quantity,
                unit=UNIT_LABELS.get(item.unit_type, item.unit_type.upper()),
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
        invoice.save(update_fields=["taxable_total", "cgst_total", "sgst_total", "igst_total", "wallet_discount", "round_off", "amount_in_words"])
        order.invoice_from_address = from_address
        order.status = Order.PACKED
        order.save(update_fields=["invoice_from_address", "status", "updated_at"])
        return invoice
