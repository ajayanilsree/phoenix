from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from accounts.decorators import user_role
from .invoices import InvoiceGenerationError, store_invoice_pdf
from .models import Invoice


def _invoices_for(user):
    qs = Invoice.objects.select_related("order", "order__customer").prefetch_related("items")
    role = user_role(user)
    if role in {"customer", "agent"}:
        qs = qs.filter(order__customer=user)
    return qs


def _allowed(user, role):
    return user.is_superuser or user_role(user) == role


def _private(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    return response


def _sidebar_for(role):
    return {
        "admin": "dashboard/admin/_sidebar.html",
        "staff": "staff_portal/_sidebar.html",
        "customer": "customers/_sidebar.html",
        "agent": "agents/_sidebar.html",
    }[role]


@login_required
@never_cache
def invoice_list(request, role, title, detail_url="", pdf_url=""):
    if not _allowed(request.user, role):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    return _private(render(request, "orders/invoice_list.html", {"invoices": _invoices_for(request.user), "title": title, "invoice_detail_url": detail_url, "invoice_pdf_url": pdf_url, "sidebar_template": _sidebar_for(role)}))


@login_required
@never_cache
def invoice_detail(request, invoice_id, role, title="Invoice", detail_url="", pdf_url=""):
    if not _allowed(request.user, role):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    invoice = get_object_or_404(_invoices_for(request.user), pk=invoice_id)
    total_quantity = sum(item.quantity for item in invoice.items.all())
    return _private(render(request, "orders/invoice_detail.html", {"invoice": invoice, "title": title, "sidebar_template": _sidebar_for(role), "invoice_detail_url": detail_url, "invoice_pdf_url": pdf_url, "company_gstin": invoice.company_gstin or getattr(settings, "INVOICE_COMPANY_GSTIN", ""), "total_quantity": total_quantity}))


@login_required
@never_cache
def invoice_pdf(request, invoice_id, role):
    if not _allowed(request.user, role):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    invoice = get_object_or_404(_invoices_for(request.user), pk=invoice_id)

    # Invoice PDFs are media files, not generated into Render's ephemeral
    # filesystem. Regenerate only for legacy invoices with no stored file.
    if not invoice.pdf_file:
        try:
            store_invoice_pdf(invoice)
        except InvoiceGenerationError as error:
            return HttpResponse(str(error), status=503)
        invoice.refresh_from_db()
    try:
        file_handle = invoice.pdf_file.open("rb")
    except Exception:
        from .invoices import logger
        logger.exception("Stored invoice PDF could not be opened for invoice %s", invoice.invoice_number)
        return HttpResponse("Invoice PDF is temporarily unavailable.", status=503)
    response = FileResponse(file_handle, content_type="application/pdf", as_attachment=True, filename=f"{invoice.invoice_number}.pdf")
    return _private(response)

    # Kept below as a local fallback for development environments that have
    # legacy invoice rows without a FileField-backed PDF.
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return HttpResponse("Invoice PDF support is not installed.", status=503)

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    font_name = "Helvetica"
    bold_font_name = "Helvetica-Bold"
    font_candidates = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("C:/Windows/Fonts/arial.ttf")]
    bold_candidates = [Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")]
    for candidate in font_candidates:
        if candidate.exists():
            pdfmetrics.registerFont(TTFont("PhoenixUnicode", str(candidate)))
            font_name = "PhoenixUnicode"
            break
    for candidate in bold_candidates:
        if candidate.exists():
            pdfmetrics.registerFont(TTFont("PhoenixUnicodeBold", str(candidate)))
            bold_font_name = "PhoenixUnicodeBold"
            break
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = font_name
    styles["Normal"].fontSize = 8.5
    styles["Normal"].leading = 11
    styles["Heading2"].fontName = bold_font_name
    styles["Heading2"].textColor = colors.HexColor("#071b33")
    story = []
    logo = Path(settings.BASE_DIR) / "static" / "img" / "phoenix-logo-brown.png"
    header = []
    if logo.exists():
        header.append(Image(str(logo), width=32 * mm, height=16 * mm))
    company_gstin = invoice.company_gstin or getattr(settings, "INVOICE_COMPANY_GSTIN", "")
    header.append(Paragraph(f"<b>{invoice.company_name}</b><br/>{invoice.company_address or ''}<br/>{invoice.company_email}<br/>Mobile: {invoice.company_mobile}<br/><b>GSTIN: {company_gstin or '-'}</b>", styles["Normal"]))
    header.append(Paragraph(f"<b>GST TAX INVOICE</b><br/><br/>Invoice No: {invoice.invoice_number}<br/>Invoice Date: {invoice.invoice_date:%d-%m-%Y}<br/>Order No: {invoice.order.order_number}<br/>Order Date: {invoice.order.created_at:%d-%m-%Y}", styles["Normal"]))
    table = Table([header], colWidths=[42 * mm, 84 * mm, 60 * mm])
    table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7b8a5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTNAME", (0, 0), (-1, -1), font_name), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [table, Spacer(1, 5 * mm)]
    party = Table([[Paragraph(f"<b>Billed To</b><br/>{invoice.billing_name}<br/>{invoice.billing_address}<br/>{invoice.billing_phone}<br/>GSTIN: {invoice.billing_gstin or '-'}", styles["Normal"]), Paragraph(f"<b>Shipped To</b><br/>{invoice.shipping_name}<br/>{invoice.shipping_address}<br/>{invoice.shipping_phone}<br/>{invoice.shipping_state or ''} {invoice.shipping_gstin or ''}", styles["Normal"])]], colWidths=[93 * mm, 93 * mm])
    party.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7b8a5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 7)]))
    story += [party, Spacer(1, 5 * mm)]
    rows = [["Sl No", "Description", "HSN", "GST %", "Qty", "Unit", "Rate", "Amount"]]
    for item in invoice.items.all():
        rows.append([item.line_number, item.description, item.hsn_code or "-", f"{item.gst_rate}%", item.quantity, item.unit, f"₹{item.taxable_unit_rate}", f"₹{item.line_total}"])
    rows.append(["", "Total", "", "", sum(i.quantity for i in invoice.items.all()), "", "", f"₹{invoice.grand_total}"])
    items = Table(rows, colWidths=[9 * mm, 62 * mm, 21 * mm, 16 * mm, 14 * mm, 15 * mm, 25 * mm, 27 * mm], repeatRows=1)
    items.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7b8a5")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#071b33")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0e8df")), ("FONTNAME", (0, 0), (-1, 0), bold_font_name), ("FONTNAME", (0, 1), (-1, -1), font_name), ("ALIGN", (3, 1), (-1, -1), "RIGHT"), ("ALIGN", (0, 0), (2, -1), "LEFT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("PADDING", (0, 0), (-1, -1), 5)]))
    story += [items, Spacer(1, 5 * mm)]
    totals = Table([["Taxable Total", f"₹{invoice.taxable_total}"], ["CGST", f"₹{invoice.cgst_total}"], ["SGST", f"₹{invoice.sgst_total}"], ["Grand Total", f"₹{invoice.grand_total}"]], colWidths=[145 * mm, 44 * mm])
    totals.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7b8a5")), ("FONTNAME", (0, 0), (-1, -1), font_name), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), bold_font_name), ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d7b06a")), ("PADDING", (0, 0), (-1, -1), 6)]))
    signature_path = Path(settings.BASE_DIR) / "static" / "img" / "invoice-signature.png"
    signature_image = Image(str(signature_path), width=42 * mm, height=18 * mm) if signature_path.exists() else Spacer(42 * mm, 18 * mm)
    signature_block = Table([[Paragraph("<b>For PHOENIX INTERIOR HUB</b>", styles["Normal"])], [signature_image], [Paragraph("<b>AUTHORISED SIGNATORY</b>", styles["Normal"])]], colWidths=[189 * mm])
    signature_block.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("ALIGN", (0, 0), (-1, -1), "LEFT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [totals, Spacer(1, 5 * mm), Paragraph(f"Amount in words: <b>{invoice.amount_in_words}</b>", styles["Normal"]), Spacer(1, 8 * mm), Paragraph(f"<b>From Address</b><br/>{invoice.from_address.replace(chr(10), '<br/>')}", styles["Normal"]), Spacer(1, 8 * mm), signature_block]
    doc.build(story)
    stream.seek(0)
    response = FileResponse(stream, content_type="application/pdf", as_attachment=True, filename=f"{invoice.invoice_number}.pdf")
    return _private(response)


def admin_invoices(request):
    return invoice_list(request, "admin", "Invoices", "admin_invoice_detail", "admin_invoice_pdf")


def admin_invoice_detail(request, invoice_id):
    return invoice_detail(request, invoice_id, "admin", "Invoice", "admin_invoice_detail", "admin_invoice_pdf")


def admin_invoice_pdf(request, invoice_id):
    return invoice_pdf(request, invoice_id, "admin")


def employee_invoices(request):
    return invoice_list(request, "staff", "Invoices", "employee_invoice_detail", "employee_invoice_pdf")


def employee_invoice_detail(request, invoice_id):
    return invoice_detail(request, invoice_id, "staff", "Invoice", "employee_invoice_detail", "employee_invoice_pdf")


def employee_invoice_pdf(request, invoice_id):
    return invoice_pdf(request, invoice_id, "staff")


def customer_invoices(request):
    return invoice_list(request, "customer", "My Invoices", "customer_invoice_detail", "customer_invoice_pdf")


def customer_invoice_detail(request, invoice_id):
    return invoice_detail(request, invoice_id, "customer", "Invoice", "customer_invoice_detail", "customer_invoice_pdf")


def customer_invoice_pdf(request, invoice_id):
    return invoice_pdf(request, invoice_id, "customer")


def agent_invoices(request):
    return invoice_list(request, "agent", "My Invoices", "agent_invoice_detail", "agent_invoice_pdf")


def agent_invoice_detail(request, invoice_id):
    return invoice_detail(request, invoice_id, "agent", "Invoice", "agent_invoice_detail", "agent_invoice_pdf")


def agent_invoice_pdf(request, invoice_id):
    return invoice_pdf(request, invoice_id, "agent")
