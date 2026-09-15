from io import BytesIO
from pathlib import Path

from django.conf import settings


def render_invoice_pdf(invoice):
    """Render the invoice snapshot without writing to the application disk."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
    header.append(Paragraph(f"<b>{invoice.company_name}</b><br/>{invoice.company_address or ''}<br/>{invoice.company_email}<br/>Mobile: {invoice.company_mobile}<br/><b>GSTIN: {invoice.company_gstin or '-'}</b>", styles["Normal"]))
    header.append(Paragraph(f"<b>GST TAX INVOICE</b><br/><br/>Invoice No: {invoice.invoice_number}<br/>Invoice Date: {invoice.invoice_date:%d-%m-%Y}<br/>Order No: {invoice.order.order_number}<br/>Order Date: {invoice.order.created_at:%d-%m-%Y}", styles["Normal"]))
    table = Table([header], colWidths=[42 * mm, 84 * mm, 60 * mm])
    table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7b8a5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTNAME", (0, 0), (-1, -1), font_name), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [table, Spacer(1, 5 * mm)]
    party = Table([[Paragraph(f"<b>Billed To</b><br/>{invoice.billing_name}<br/>{invoice.billing_address}<br/>{invoice.billing_phone}<br/>GSTIN: {invoice.billing_gstin or '-'}", styles["Normal"]), Paragraph(f"<b>Shipped To</b><br/>{invoice.shipping_name}<br/>{invoice.shipping_address}<br/>{invoice.shipping_phone}<br/>{invoice.shipping_state or ''} {invoice.shipping_gstin or ''}", styles["Normal"])]], colWidths=[93 * mm, 93 * mm])
    party.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c7b8a5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 7)]))
    story += [party, Spacer(1, 5 * mm)]
    rows = [["Sl No", "Description", "HSN", "GST %", "Qty", "Unit", "Rate", "Amount"]]
    items = list(invoice.items.all())
    for item in items:
        rows.append([item.line_number, item.description, item.hsn_code or "-", f"{item.gst_rate}%", item.quantity, item.unit, f"₹{item.taxable_unit_rate}", f"₹{item.line_total}"])
    rows.append(["", "Total", "", "", sum(item.quantity for item in items), "", "", f"₹{invoice.grand_total}"])
    item_table = Table(rows, colWidths=[9 * mm, 62 * mm, 21 * mm, 16 * mm, 14 * mm, 15 * mm, 25 * mm, 27 * mm], repeatRows=1)
    item_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7b8a5")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#071b33")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f0e8df")), ("FONTNAME", (0, 0), (-1, 0), bold_font_name), ("FONTNAME", (0, 1), (-1, -1), font_name), ("ALIGN", (3, 1), (-1, -1), "RIGHT"), ("ALIGN", (0, 0), (2, -1), "LEFT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("PADDING", (0, 0), (-1, -1), 5)]))
    story += [item_table, Spacer(1, 5 * mm)]
    totals = Table([["Taxable Total", f"₹{invoice.taxable_total}"], ["CGST", f"₹{invoice.cgst_total}"], ["SGST", f"₹{invoice.sgst_total}"], ["Grand Total", f"₹{invoice.grand_total}"]], colWidths=[145 * mm, 44 * mm])
    totals.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c7b8a5")), ("FONTNAME", (0, 0), (-1, -1), font_name), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), bold_font_name), ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#d7b06a")), ("PADDING", (0, 0), (-1, -1), 6)]))
    signature_path = Path(settings.BASE_DIR) / "static" / "img" / "invoice-signature.png"
    signature_image = Image(str(signature_path), width=42 * mm, height=18 * mm) if signature_path.exists() else Spacer(42 * mm, 18 * mm)
    signature_block = Table([[Paragraph("<b>For PHOENIX INTERIOR HUB</b>", styles["Normal"])], [signature_image], [Paragraph("<b>AUTHORISED SIGNATORY</b>", styles["Normal"])]], colWidths=[189 * mm])
    signature_block.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#071b33")), ("ALIGN", (0, 0), (-1, -1), "LEFT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [totals, Spacer(1, 5 * mm), Paragraph(f"Amount in words: <b>{invoice.amount_in_words}</b>", styles["Normal"]), Spacer(1, 8 * mm), Paragraph(f"<b>From Address</b><br/>{invoice.from_address.replace(chr(10), '<br/>')}", styles["Normal"]), Spacer(1, 8 * mm), signature_block]
    doc.build(story)
    return stream.getvalue()
