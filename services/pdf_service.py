from io import BytesIO
from pathlib import Path
import sys
import textwrap

for _site_packages in sorted((Path("venv/lib")).glob("python*/site-packages")):
    site_packages_path = str(_site_packages.resolve())
    if site_packages_path not in sys.path:
        sys.path.append(site_packages_path)

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def _layout_key(slug):
    parts = str(slug or "").split("_", 1)
    return parts[1] if len(parts) == 2 else "modern_clean"


def _color(value, alpha=1):
    color = colors.HexColor(value)
    if alpha == 1:
        return color
    return colors.Color(color.red, color.green, color.blue, alpha=alpha)


def _fmt(value):
    try:
        return f"{float(value or 0):,.2f}"
    except Exception:
        return "0.00"


def _fmt_date(value):
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y")
    return str(value)


def _doc_labels(document):
    is_quote = document.get("document_type") == "quotation"
    return {
        "is_quote": is_quote,
        "heading": "QUOTATION" if is_quote else "INVOICE",
        "date_label": "Valid Until" if is_quote else "Due Date",
        "date_value": document.get("valid_until") if is_quote else document.get("due_date"),
        "total_label": "Estimated Total" if is_quote else "Amount Due",
    }


def _logo_path(logo_url):
    if not logo_url or not str(logo_url).startswith("/static/"):
        return None
    relative = str(logo_url).lstrip("/")
    path = Path.cwd() / relative
    return path if path.exists() else None


def _draw_logo(pdf, logo_url, x, y, width=24 * mm, height=24 * mm):
    path = _logo_path(logo_url)
    if not path:
        return False
    pdf.drawImage(ImageReader(str(path)), x, y, width=width, height=height, preserveAspectRatio=True, mask="auto")
    return True


def _fit(text, limit):
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _paragraph_lines(text, width):
    lines = []
    for raw in str(text or "").splitlines() or [""]:
        wrapped = textwrap.wrap(raw, width=width) or [""]
        lines.extend(wrapped)
    return lines


def _draw_paragraph(pdf, text, x, y, width=64, font="Helvetica", size=10, leading=14, color="#111827", max_lines=6):
    pdf.setFont(font, size)
    pdf.setFillColor(_color(color))
    cursor = y
    for line in _paragraph_lines(text, width)[:max_lines]:
        pdf.drawString(x, cursor, line)
        cursor -= leading
    return cursor


def _draw_kv(pdf, x, y, label, value, label_font="Helvetica-Bold", value_font="Helvetica", label_color="#64748b", value_color="#111827"):
    pdf.setFont(label_font, 8)
    pdf.setFillColor(_color(label_color))
    pdf.drawString(x, y, label.upper())
    pdf.setFont(value_font, 10)
    pdf.setFillColor(_color(value_color))
    pdf.drawString(x, y - 11, _fit(value, 34))


def _draw_detail_box(pdf, x, y_top, width, height, title, lines, stroke="#d8dee7", fill=None, title_color="#64748b", text_color="#111827"):
    if fill:
        pdf.setFillColor(_color(fill))
        pdf.roundRect(x, y_top - height, width, height, 5 * mm, fill=1, stroke=0)
    pdf.setStrokeColor(_color(stroke))
    pdf.roundRect(x, y_top - height, width, height, 5 * mm, fill=0, stroke=1)
    pdf.setFillColor(_color(title_color))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(x + 12, y_top - 18, title.upper())
    pdf.setFillColor(_color(text_color))
    pdf.setFont("Helvetica", 10)
    cursor = y_top - 34
    for line in lines[:6]:
        pdf.drawString(x + 12, cursor, _fit(line, 50))
        cursor -= 13


def _draw_table(pdf, x, y_top, width, headers, rows, col_widths, header_bg="#eef2ff", header_text="#334155", row_text="#111827", line_color="#dbe4f0", row_height=18, alt_fill=None):
    current_y = y_top
    pdf.setFillColor(_color(header_bg))
    pdf.roundRect(x, current_y - row_height, width, row_height, 3 * mm, fill=1, stroke=0)
    pdf.setFillColor(_color(header_text))
    pdf.setFont("Helvetica-Bold", 8)
    cursor_x = x + 8
    for idx, header in enumerate(headers):
        align_right = idx > 0
        if align_right:
            pdf.drawRightString(cursor_x + col_widths[idx] - 8, current_y - 12, header.upper())
        else:
            pdf.drawString(cursor_x, current_y - 12, header.upper())
        cursor_x += col_widths[idx]
    current_y -= row_height
    pdf.setStrokeColor(_color(line_color))
    for row_index, row in enumerate(rows):
        if alt_fill and row_index % 2 == 1:
            pdf.setFillColor(_color(alt_fill))
            pdf.rect(x, current_y - row_height, width, row_height, fill=1, stroke=0)
        pdf.line(x, current_y - row_height, x + width, current_y - row_height)
        pdf.setFillColor(_color(row_text))
        pdf.setFont("Helvetica", 9)
        cursor_x = x + 8
        for idx, value in enumerate(row):
            if idx > 0:
                pdf.drawRightString(cursor_x + col_widths[idx] - 8, current_y - 12, _fit(value, 18))
            else:
                pdf.drawString(cursor_x, current_y - 12, _fit(value, 42))
            cursor_x += col_widths[idx]
        current_y -= row_height
    return current_y


def _money_rows(document, total_label):
    return [
        ("Subtotal", f"N$ {_fmt(document.get('subtotal'))}"),
        ("Tax", f"N$ {_fmt(document.get('tax'))}"),
        ("Discount", f"N$ {_fmt(document.get('discount'))}"),
        (total_label, f"N$ {_fmt(document.get('total'))}"),
    ]


def _draw_totals_box(pdf, x, y_top, width, rows, fill="#ffffff", stroke="#dbe4f0", text="#111827", highlight="#111827", dark=False):
    height = 18 + len(rows) * 18
    if fill:
        pdf.setFillColor(_color(fill))
        pdf.roundRect(x, y_top - height, width, height, 5 * mm, fill=1, stroke=0)
    pdf.setStrokeColor(_color(stroke))
    pdf.roundRect(x, y_top - height, width, height, 5 * mm, fill=0, stroke=1)
    cursor = y_top - 18
    for idx, (label, value) in enumerate(rows):
        is_total = idx == len(rows) - 1
        pdf.setFillColor(_color(highlight if is_total else text))
        pdf.setFont("Helvetica-Bold" if is_total else "Helvetica", 11 if is_total else 9)
        pdf.drawString(x + 12, cursor, label)
        pdf.drawRightString(x + width - 12, cursor, value)
        cursor -= 18
    return y_top - height


def _draw_watermark(pdf, width, height, label, text_color, size, angle, x=None, y=None, alpha=0.12):
    if not label:
        return
    pdf.saveState()
    pdf.setFillColor(_color(text_color, alpha=alpha))
    pdf.setFont("Helvetica-Bold", size)
    pdf.translate(x or width / 2, y or height / 2)
    pdf.rotate(angle)
    pdf.drawCentredString(0, 0, label)
    pdf.restoreState()


def _common_rows(items):
    return [
        [
            str(item.get("item_name") or "Item"),
            str(item.get("quantity") or 1),
            f"N$ {_fmt(item.get('unit_price'))}",
            f"N$ {_fmt(item.get('total'))}",
        ]
        for item in items
    ]


def draw_modern_clean(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    _draw_watermark(pdf, width, height, watermark_label, "#2563eb", 46, 32, x=width - 75 * mm, y=height / 2)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.setFillColor(_color("#64748b"))
    x = 18 * mm
    logo_drawn = _draw_logo(pdf, document.get("business_logo_url"), x, height - 38 * mm)
    x_text = x + (30 * mm if logo_drawn else 0)
    pdf.drawString(x_text, height - 18 * mm, labels["heading"])
    pdf.setFont("Helvetica-Bold", 22)
    pdf.setFillColor(_color("#111827"))
    pdf.drawString(x_text, height - 28 * mm, _fit(document.get("business_name") or "Business", 26))
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(_color("#475569"))
    pdf.drawString(x_text, height - 35 * mm, _fit(document.get("business_email"), 40))
    pdf.drawString(x_text, height - 41 * mm, _fit(document.get("business_phone"), 40))
    pdf.drawString(x_text, height - 47 * mm, _fit(document.get("business_address"), 52))
    pdf.setFillColor(_color("#f8fbff"))
    pdf.roundRect(126 * mm, height - 48 * mm, 66 * mm, 28 * mm, 5 * mm, fill=1, stroke=0)
    pdf.setStrokeColor(_color("#dbe4f0"))
    pdf.roundRect(126 * mm, height - 48 * mm, 66 * mm, 28 * mm, 5 * mm, fill=0, stroke=1)
    _draw_kv(pdf, 132 * mm, height - 28 * mm, "Number", document.get("document_number"))
    _draw_kv(pdf, 160 * mm, height - 28 * mm, labels["date_label"], _fmt_date(labels["date_value"]))
    _draw_detail_box(pdf, 18 * mm, height - 58 * mm, 82 * mm, 30 * mm, "Bill To" if not labels["is_quote"] else "Prepared For", [document.get("customer_name"), document.get("customer_email"), document.get("customer_phone"), document.get("customer_address")], fill="#ffffff")
    _draw_detail_box(pdf, 110 * mm, height - 58 * mm, 82 * mm, 30 * mm, "Summary" if not labels["is_quote"] else "Approval", [document.get("notes"), "Payment details and totals appear below." if not labels["is_quote"] else "Review the scope and sign to accept the quote."], fill="#ffffff")
    y = _draw_table(pdf, 18 * mm, height - 98 * mm, 174 * mm, ["Item", "Qty", "Unit", "Total"], _common_rows(items), [92 * mm, 22 * mm, 30 * mm, 30 * mm], alt_fill="#fbfdff")
    _draw_totals_box(pdf, 128 * mm, y - 10, 64 * mm, _money_rows(document, labels["total_label"]), fill="#ffffff", stroke="#dbe4f0")
    _draw_paragraph(pdf, document.get("notes"), 18 * mm, 60 * mm, width=62, color="#334155")
    right_text = document.get("payment_details") if not labels["is_quote"] else "Accept Quote: Name ____________________  Signature ____________________"
    _draw_paragraph(pdf, right_text, 110 * mm, 60 * mm, width=50, color="#334155")


def draw_luxury_gold(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    pdf.setFillColor(_color("#111111"))
    pdf.rect(0, height - 54 * mm, width, 54 * mm, fill=1, stroke=0)
    pdf.setFillColor(_color("#f1d78c"))
    pdf.rect(0, height - 56 * mm, width, 2 * mm, fill=1, stroke=0)
    _draw_watermark(pdf, width, height, watermark_label, "#b88a22", 60, -18, alpha=0.10)
    if not _draw_logo(pdf, document.get("business_logo_url"), width / 2 - 12 * mm, height - 34 * mm):
        pdf.setFont("Helvetica-Bold", 30)
        pdf.setFillColor(_color("#f1d78c"))
        pdf.drawCentredString(width / 2, height - 22 * mm, labels["heading"])
    pdf.setFillColor(_color("#f8edd2"))
    pdf.setFont("Times-Bold", 22)
    pdf.drawCentredString(width / 2, height - 40 * mm, _fit(document.get("business_name") or "Business", 28))
    pdf.setFont("Times-Roman", 10)
    pdf.drawCentredString(width / 2, height - 46 * mm, _fit(document.get("business_address"), 64))
    pdf.setFillColor(_color("#8d6a21"))
    pdf.setFont("Times-Bold", 28)
    pdf.drawString(18 * mm, height - 72 * mm, labels["heading"])
    pdf.setFillColor(_color("#17120a"))
    pdf.setFont("Times-Roman", 11)
    pdf.drawString(18 * mm, height - 82 * mm, _fit(document.get("customer_name"), 32))
    pdf.drawString(18 * mm, height - 88 * mm, _fit(document.get("customer_address"), 48))
    pdf.drawRightString(192 * mm, height - 72 * mm, _fit(document.get("document_number"), 22))
    pdf.drawRightString(192 * mm, height - 80 * mm, f"Issued {_fmt_date(document.get('issue_date'))}")
    pdf.drawRightString(192 * mm, height - 88 * mm, f"{labels['date_label']} {_fmt_date(labels['date_value'])}")
    y = _draw_table(pdf, 18 * mm, height - 104 * mm, 174 * mm, ["Description", "Qty", "Rate", "Amount"], _common_rows(items), [92 * mm, 20 * mm, 30 * mm, 32 * mm], header_bg="#fff7e2", header_text="#8d6a21", line_color="#ead8b1", alt_fill="#fffdfa")
    _draw_paragraph(pdf, document.get("notes"), 18 * mm, y - 20, width=58, font="Times-Roman", size=11, leading=15, color="#3b3427")
    _draw_paragraph(pdf, document.get("terms"), 18 * mm, y - 64, width=58, font="Times-Roman", size=11, leading=15, color="#3b3427")
    _draw_totals_box(pdf, 124 * mm, y - 8, 68 * mm, _money_rows(document, labels["total_label"]), fill="#fffaf0", stroke="#d6bc81", text="#4d3b16", highlight="#8d6a21")
    pdf.setFillColor(_color("#14110d"))
    pdf.rect(0, 0, width, 18 * mm, fill=1, stroke=0)
    pdf.setFillColor(_color("#e7d4a1"))
    pdf.setFont("Times-Roman", 10)
    footer_text = "Accept Quote and return signed approval." if labels["is_quote"] else document.get("payment_details") or "Prepared with premium billing presentation."
    pdf.drawString(18 * mm, 8 * mm, _fit(footer_text, 82))


def draw_corporate_blue(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    sidebar_w = 58 * mm
    pdf.setFillColor(_color("#133f95"))
    pdf.rect(0, 0, sidebar_w, height, fill=1, stroke=0)
    _draw_watermark(pdf, width, height, watermark_label, "#1d4ed8", 34, -90, x=width - 15 * mm, y=height / 2)
    _draw_logo(pdf, document.get("business_logo_url"), 12 * mm, height - 36 * mm, width=26 * mm, height=26 * mm)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(12 * mm, height - 46 * mm, _fit(document.get("business_name"), 15))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(12 * mm, height - 54 * mm, _fit(document.get("business_email"), 26))
    pdf.drawString(12 * mm, height - 60 * mm, _fit(document.get("business_phone"), 26))
    pdf.drawString(12 * mm, height - 66 * mm, _fit(document.get("business_address"), 28))
    pdf.setFillColor(_color("#eef5ff"))
    pdf.roundRect(70 * mm, height - 42 * mm, 122 * mm, 26 * mm, 5 * mm, fill=1, stroke=0)
    pdf.setStrokeColor(_color("#cbdcf7"))
    pdf.roundRect(70 * mm, height - 42 * mm, 122 * mm, 26 * mm, 5 * mm, fill=0, stroke=1)
    pdf.setFillColor(_color("#0f172a"))
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(76 * mm, height - 28 * mm, labels["heading"])
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawRightString(186 * mm, height - 28 * mm, _fit(document.get("document_number"), 22))
    _draw_detail_box(pdf, 70 * mm, height - 52 * mm, 58 * mm, 30 * mm, "Prepared For" if labels["is_quote"] else "Bill To", [document.get("customer_name"), document.get("customer_email"), document.get("customer_phone"), document.get("customer_address")], stroke="#d9e5fb", fill="#ffffff")
    _draw_detail_box(pdf, 134 * mm, height - 52 * mm, 58 * mm, 30 * mm, "Decision Summary" if labels["is_quote"] else "Finance Summary", [document.get("notes"), f"{labels['date_label']}: {_fmt_date(labels['date_value'])}"], stroke="#d9e5fb", fill="#ffffff")
    y = _draw_table(pdf, 70 * mm, height - 92 * mm, 122 * mm, ["Line Item", "Units", "Price", "Line Total"], _common_rows(items), [60 * mm, 16 * mm, 22 * mm, 24 * mm], header_bg="#e8f1ff", header_text="#33558f", line_color="#dde8fb", alt_fill="#f7faff")
    _draw_paragraph(pdf, document.get("terms"), 70 * mm, y - 18, width=46, color="#334155")
    right_text = "Accept Quote: Authorized by ____________________" if labels["is_quote"] else document.get("payment_details")
    _draw_paragraph(pdf, right_text, 134 * mm, y - 18, width=32, color="#334155")
    _draw_totals_box(pdf, 132 * mm, 54 * mm, 60 * mm, _money_rows(document, labels["total_label"]), fill="#eef5ff", stroke="#cbdcf7", text="#224073", highlight="#0f172a")


def draw_retail_receipt(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    slip_x = width / 2 - 43 * mm
    slip_w = 86 * mm
    pdf.setFillColor(_color("#f1f1f1"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.rect(slip_x, 16 * mm, slip_w, height - 32 * mm, fill=1, stroke=0)
    pdf.setStrokeColor(_color("#d8d8d8"))
    pdf.rect(slip_x, 16 * mm, slip_w, height - 32 * mm, fill=0, stroke=1)
    _draw_watermark(pdf, width, height, watermark_label, "#111111", 28, -90, x=width / 2, y=height / 2)
    y = height - 28 * mm
    _draw_logo(pdf, document.get("business_logo_url"), width / 2 - 10 * mm, y - 10 * mm, width=20 * mm, height=20 * mm)
    pdf.setFillColor(_color("#111111"))
    pdf.setFont("Courier-Bold", 14)
    pdf.drawCentredString(width / 2, y - 14 * mm, _fit(document.get("business_name"), 20))
    pdf.setFont("Courier", 8)
    pdf.drawCentredString(width / 2, y - 19 * mm, _fit(document.get("business_address"), 28))
    pdf.drawCentredString(width / 2, y - 24 * mm, _fit(document.get("business_phone"), 18))
    pdf.line(slip_x + 6 * mm, y - 28 * mm, slip_x + slip_w - 6 * mm, y - 28 * mm)
    pdf.setFont("Courier-Bold", 10)
    pdf.drawCentredString(width / 2, y - 35 * mm, labels["heading"])
    pdf.drawCentredString(width / 2, y - 41 * mm, _fit(document.get("document_number"), 22))
    bx = slip_x + 18 * mm
    for idx in range(20):
        bar_h = 10 * mm if idx % 2 == 0 else 6 * mm
        pdf.rect(bx + idx * 2.7 * mm, y - 53 * mm, 1.1 * mm, bar_h, fill=1, stroke=0)
    pdf.setFont("Courier", 8)
    pdf.drawCentredString(width / 2, y - 58 * mm, f"{labels['date_label']}: {_fit(_fmt_date(labels['date_value']), 16)}")
    pdf.line(slip_x + 6 * mm, y - 62 * mm, slip_x + slip_w - 6 * mm, y - 62 * mm)
    row_y = y - 70 * mm
    pdf.drawString(slip_x + 8 * mm, row_y, _fit(f"Customer: {document.get('customer_name')}", 26))
    row_y -= 8
    pdf.drawString(slip_x + 8 * mm, row_y, _fit(f"Ref: {document.get('customer_phone') or document.get('customer_email')}", 26))
    row_y -= 10
    pdf.line(slip_x + 6 * mm, row_y, slip_x + slip_w - 6 * mm, row_y)
    row_y -= 10
    pdf.setFont("Courier", 8)
    for item in items[:10]:
        pdf.drawString(slip_x + 8 * mm, row_y, _fit(f"{item.get('item_name')} x{item.get('quantity')}", 22))
        pdf.drawRightString(slip_x + slip_w - 8 * mm, row_y, f"N$ {_fmt(item.get('total'))}")
        row_y -= 8
        pdf.line(slip_x + 8 * mm, row_y + 3, slip_x + slip_w - 8 * mm, row_y + 3)
    for label, value in _money_rows(document, labels["total_label"]):
        pdf.drawString(slip_x + 8 * mm, row_y, label)
        font_name = "Courier-Bold" if label == labels["total_label"] else "Courier"
        font_size = 13 if label == labels["total_label"] else 8
        pdf.setFont(font_name, font_size)
        pdf.drawRightString(slip_x + slip_w - 8 * mm, row_y, value)
        pdf.setFont("Courier", 8)
        row_y -= 10
    pdf.line(slip_x + 6 * mm, row_y + 3, slip_x + slip_w - 6 * mm, row_y + 3)
    _draw_paragraph(pdf, document.get("terms"), slip_x + 8 * mm, row_y - 10, width=26, font="Courier", size=8, leading=10, color="#111111", max_lines=5)


def draw_restaurant_order(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    pdf.setFillColor(_color("#fff8f1"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(_color("#6f260d"))
    pdf.roundRect(16 * mm, height - 66 * mm, width - 32 * mm, 50 * mm, 8 * mm, fill=1, stroke=0)
    _draw_watermark(pdf, width, height, watermark_label, "#fff1e5", 30, -12, x=width - 36 * mm, y=height - 26 * mm, alpha=0.16)
    _draw_logo(pdf, document.get("business_logo_url"), width - 38 * mm, height - 34 * mm, width=20 * mm, height=20 * mm)
    pdf.setFillColor(_color("#fff5eb"))
    pdf.setFont("Times-Bold", 24)
    pdf.drawString(24 * mm, height - 28 * mm, _fit(document.get("business_name"), 28))
    pdf.setFont("Times-Roman", 10)
    pdf.drawString(24 * mm, height - 36 * mm, _fit(document.get("business_address"), 52))
    pdf.drawString(24 * mm, height - 42 * mm, _fit(document.get("business_phone"), 26))
    pdf.setFont("Times-Bold", 24)
    pdf.drawRightString(width - 24 * mm, height - 28 * mm, labels["heading"])
    pdf.setFont("Times-Roman", 10)
    pdf.drawRightString(width - 24 * mm, height - 36 * mm, _fit(document.get("document_number"), 22))
    pdf.drawRightString(width - 24 * mm, height - 42 * mm, f"{labels['date_label']} {_fmt_date(labels['date_value'])}")
    _draw_detail_box(pdf, 16 * mm, height - 74 * mm, 84 * mm, 32 * mm, "Customer / Event", [document.get("customer_name"), document.get("customer_phone"), document.get("customer_email"), document.get("customer_address")], stroke="#f1c08a", fill="#ffffff", title_color="#9a3412", text_color="#431407")
    _draw_detail_box(pdf, 108 * mm, height - 74 * mm, 84 * mm, 32 * mm, "Delivery / Pickup", [document.get("notes"), "Catering event details and service timing." if labels["is_quote"] else "Kitchen and fulfilment notes."], stroke="#f1c08a", fill="#fff7ee", title_color="#9a3412", text_color="#431407")
    y = _draw_table(pdf, 16 * mm, height - 116 * mm, 176 * mm, ["Menu Item", "Qty", "Rate", "Line Total"], _common_rows(items), [94 * mm, 20 * mm, 28 * mm, 34 * mm], header_bg="#fff0dd", header_text="#9a3412", line_color="#f1d0af", alt_fill="#fffaf3")
    _draw_paragraph(pdf, document.get("terms"), 16 * mm, y - 18, width=58, font="Times-Roman", size=10, leading=14, color="#7c2d12")
    right_text = "Accept Quote: Event approval signature ____________________" if labels["is_quote"] else document.get("payment_details")
    _draw_paragraph(pdf, right_text, 114 * mm, y - 18, width=42, font="Times-Roman", size=10, leading=14, color="#7c2d12")
    _draw_totals_box(pdf, 122 * mm, 56 * mm, 70 * mm, _money_rows(document, labels["total_label"]), fill="#ffffff", stroke="#f1c08a", text="#7c2d12", highlight="#431407")


def draw_transport_trip(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    pdf.setFillColor(_color("#f3f8fe"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(_color("#10233f"))
    pdf.roundRect(16 * mm, height - 60 * mm, width - 32 * mm, 42 * mm, 8 * mm, fill=1, stroke=0)
    _draw_watermark(pdf, width, height, watermark_label, "#0ea5e9", 36, -18, x=28 * mm, y=24 * mm)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(24 * mm, height - 28 * mm, _fit(document.get("business_name"), 28))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(24 * mm, height - 36 * mm, _fit(document.get("business_phone"), 28))
    pdf.drawString(24 * mm, height - 42 * mm, _fit(document.get("business_email"), 38))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawRightString(width - 24 * mm, height - 28 * mm, labels["heading"])
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(width - 24 * mm, height - 36 * mm, _fit(document.get("document_number"), 22))
    pdf.drawRightString(width - 24 * mm, height - 42 * mm, f"{labels['date_label']} {_fmt_date(labels['date_value'])}")
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(_color("#b8d7f2"))
    pdf.roundRect(16 * mm, height - 72 * mm, width - 32 * mm, 24 * mm, 7 * mm, fill=1, stroke=1)
    _draw_kv(pdf, 24 * mm, height - 58 * mm, "Pickup", document.get("customer_address") or "City Pickup Point", value_color="#10233f")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.setFillColor(_color("#0f4f7d"))
    pdf.drawCentredString(width / 2, height - 62 * mm, "→")
    _draw_kv(pdf, width - 84 * mm, height - 58 * mm, "Dropoff", document.get("notes") or "Destination", value_color="#10233f")
    _draw_detail_box(pdf, 16 * mm, height - 102 * mm, 54 * mm, 24 * mm, "Passenger", [document.get("customer_name"), document.get("customer_phone")], stroke="#c9e2f7", fill="#ffffff", title_color="#0f4f7d", text_color="#10233f")
    _draw_detail_box(pdf, 77 * mm, height - 102 * mm, 54 * mm, 24 * mm, "Vehicle", ["Executive Shuttle", "Driver assigned on confirmation"], stroke="#c9e2f7", fill="#ffffff", title_color="#0f4f7d", text_color="#10233f")
    _draw_detail_box(pdf, 138 * mm, height - 102 * mm, 54 * mm, 24 * mm, "Booking Reference", [document.get("document_number"), "Estimate validity applies." if labels["is_quote"] else "Trip linked to this invoice."], stroke="#c9e2f7", fill="#ffffff", title_color="#0f4f7d", text_color="#10233f")
    y = _draw_table(pdf, 16 * mm, height - 134 * mm, 176 * mm, ["Trip Cost Breakdown", "Qty", "Rate", "Amount"], _common_rows(items), [96 * mm, 18 * mm, 28 * mm, 34 * mm], header_bg="#dff1ff", header_text="#0f4f7d", line_color="#d6e9f9", alt_fill="#f7fbff")
    _draw_paragraph(pdf, document.get("terms"), 16 * mm, y - 18, width=56, color="#334155")
    right_text = "Accept Quote: Pickup approval signature ____________________" if labels["is_quote"] else document.get("payment_details")
    _draw_paragraph(pdf, right_text, 114 * mm, y - 18, width=42, color="#334155")
    _draw_totals_box(pdf, 124 * mm, 56 * mm, 68 * mm, _money_rows(document, labels["total_label"]), fill="#ffffff", stroke="#b8d7f2", text="#0f4f7d", highlight="#10233f")


def draw_construction_progress(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    split = max(1, (len(items) + 1) // 2)
    materials = items[:split]
    labour = items[split:] or items[:1]
    pdf.setFillColor(_color("#fbf7ef"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setStrokeColor(_color("#d6a33a"))
    pdf.setFillColor(_color("#fff8ea"))
    pdf.roundRect(16 * mm, height - 60 * mm, width - 32 * mm, 42 * mm, 8 * mm, fill=1, stroke=1)
    _draw_watermark(pdf, width, height, watermark_label, "#ca8a04", 42, -28, x=width - 30 * mm, y=height / 2)
    pdf.setFillColor(_color("#292524"))
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(24 * mm, height - 28 * mm, _fit(document.get("business_name"), 28))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(24 * mm, height - 36 * mm, _fit(document.get("business_phone"), 26))
    pdf.drawString(24 * mm, height - 42 * mm, _fit(document.get("business_email"), 36))
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawRightString(width - 24 * mm, height - 28 * mm, labels["heading"])
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(width - 24 * mm, height - 36 * mm, _fit(document.get("document_number"), 24))
    pdf.drawRightString(width - 24 * mm, height - 42 * mm, f"{labels['date_label']} {_fmt_date(labels['date_value'])}")
    _draw_detail_box(pdf, 16 * mm, height - 72 * mm, 90 * mm, 28 * mm, "Client / Project", [document.get("customer_name"), document.get("customer_phone"), document.get("customer_email"), document.get("customer_address")], stroke="#ead9b3", fill="#ffffff", title_color="#8c691f", text_color="#292524")
    pdf.setFillColor(_color("#2c2418"))
    pdf.roundRect(112 * mm, height - 72 * mm, 80 * mm, 28 * mm, 5 * mm, fill=1, stroke=0)
    pdf.setFillColor(_color("#f9dfa2"))
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(118 * mm, height - 56 * mm, "PROJECT STAGE")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(118 * mm, height - 66 * mm, "Estimate Review" if labels["is_quote"] else "Progress Billing")
    y_left = _draw_table(pdf, 16 * mm, height - 110 * mm, 84 * mm, ["Materials", "Qty", "Amount"], [[str(i.get("item_name")), str(i.get("quantity")), f"N$ {_fmt(i.get('total'))}"] for i in materials], [46 * mm, 14 * mm, 24 * mm], header_bg="#f8edd0", header_text="#7c5c1c", line_color="#ead9b3", alt_fill="#fff9ec")
    y_right = _draw_table(pdf, 108 * mm, height - 110 * mm, 84 * mm, ["Labour", "Qty", "Amount"], [[str(i.get("item_name")), str(i.get("quantity")), f"N$ {_fmt(i.get('total'))}"] for i in labour], [46 * mm, 14 * mm, 24 * mm], header_bg="#f8edd0", header_text="#7c5c1c", line_color="#ead9b3", alt_fill="#fff9ec")
    bottom_y = min(y_left, y_right)
    _draw_detail_box(pdf, 16 * mm, bottom_y - 10, 84 * mm, 32 * mm, "Terms", [document.get("terms")], stroke="#ead9b3", fill="#ffffff", title_color="#8c691f", text_color="#292524")
    pdf.setStrokeColor(_color("#b4a27a"))
    pdf.line(114 * mm, bottom_y - 26, 148 * mm, bottom_y - 26)
    pdf.line(156 * mm, bottom_y - 26, 190 * mm, bottom_y - 26)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(114 * mm, bottom_y - 38, "Client Signature")
    pdf.drawString(156 * mm, bottom_y - 38, "Contractor Signature")
    _draw_totals_box(pdf, 120 * mm, 54 * mm, 72 * mm, _money_rows(document, "Quote Total" if labels["is_quote"] else "Balance Due"), fill="#fffaf0", stroke="#d6a33a", text="#7c5c1c", highlight="#292524")


def draw_medical_statement(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    pdf.setFillColor(_color("#f5fdf8"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    _draw_watermark(pdf, width, height, watermark_label, "#16a34a", 38, -22, x=40 * mm, y=height / 2)
    pdf.setFillColor(_color("#16422b"))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(16 * mm, height - 22 * mm, _fit(document.get("business_name"), 30))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(16 * mm, height - 30 * mm, _fit(document.get("business_phone"), 28))
    pdf.drawString(16 * mm, height - 36 * mm, _fit(document.get("business_email"), 36))
    pdf.drawString(16 * mm, height - 42 * mm, _fit(document.get("business_address"), 54))
    _draw_logo(pdf, document.get("business_logo_url"), width - 36 * mm, height - 34 * mm, width=20 * mm, height=20 * mm)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawRightString(width - 16 * mm, height - 22 * mm, labels["heading"])
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(width - 16 * mm, height - 30 * mm, _fit(document.get("document_number"), 22))
    pdf.drawRightString(width - 16 * mm, height - 36 * mm, f"{labels['date_label']} {_fmt_date(labels['date_value'])}")
    _draw_detail_box(pdf, 16 * mm, height - 52 * mm, 84 * mm, 30 * mm, "Patient / Customer Details", [document.get("customer_name"), document.get("customer_email"), document.get("customer_phone"), document.get("customer_address")], stroke="#b7e5c8", fill="#ffffff", title_color="#2d7b4d", text_color="#16422b")
    _draw_detail_box(pdf, 108 * mm, height - 52 * mm, 84 * mm, 30 * mm, "Service Summary", [document.get("notes")], stroke="#b7e5c8", fill="#ffffff", title_color="#2d7b4d", text_color="#16422b")
    rows = [[_fmt_date(document.get("issue_date")), str(item.get("item_name")), str(item.get("quantity")), f"N$ {_fmt(item.get('total'))}"] for item in items]
    y = _draw_table(pdf, 16 * mm, height - 94 * mm, 176 * mm, ["Service Date", "Consultation / Service", "Qty", "Amount"], rows, [36 * mm, 82 * mm, 18 * mm, 40 * mm], header_bg="#f4fff7", header_text="#2d7b4d", line_color="#dff3e6", alt_fill="#fbfffc")
    _draw_paragraph(pdf, document.get("terms"), 16 * mm, y - 16, width=58, color="#2f5d46")
    right_text = "Accept Quote: Patient approval ____________________" if labels["is_quote"] else document.get("payment_details")
    _draw_paragraph(pdf, right_text, 114 * mm, y - 16, width=40, color="#2f5d46")
    _draw_totals_box(pdf, 126 * mm, 56 * mm, 66 * mm, _money_rows(document, labels["total_label"]), fill="#ffffff", stroke="#b7e5c8", text="#2d7b4d", highlight="#16422b")
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(_color("#3b7b57"))
    pdf.drawString(16 * mm, 10 * mm, "Private health information should be handled confidentially and stored according to your clinic privacy process.")


def draw_school_fees(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    pdf.setFillColor(_color("#fffdf0"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(_color("#2045aa"))
    pdf.roundRect(16 * mm, height - 60 * mm, width - 32 * mm, 42 * mm, 8 * mm, fill=1, stroke=0)
    pdf.setFillColor(_color("#f0be2c"))
    pdf.rect(16 * mm, height - 60 * mm, width - 32 * mm, 10 * mm, fill=1, stroke=0)
    _draw_watermark(pdf, width, height, watermark_label, "#1d4ed8", 36, -18, x=width - 30 * mm, y=20 * mm)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(24 * mm, height - 30 * mm, _fit(document.get("business_name"), 30))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(24 * mm, height - 38 * mm, _fit(document.get("business_address"), 50))
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawRightString(width - 24 * mm, height - 30 * mm, labels["heading"])
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(width - 24 * mm, height - 38 * mm, _fit(document.get("document_number"), 22))
    pdf.drawRightString(width - 24 * mm, height - 44 * mm, f"{labels['date_label']} {_fmt_date(labels['date_value'])}")
    _draw_detail_box(pdf, 16 * mm, height - 72 * mm, 84 * mm, 28 * mm, "Student Details", [document.get("customer_name"), f"Parent/Guardian: {document.get('customer_email')}", f"Contact: {document.get('customer_phone')}", document.get("customer_address")], stroke="#e8d37d", fill="#ffffff", title_color="#294c94", text_color="#1e3a8a")
    _draw_detail_box(pdf, 108 * mm, height - 72 * mm, 84 * mm, 28 * mm, "Term / Grade", ["Term billing summary", "Grade record", "Status: Pending Acceptance" if labels["is_quote"] else "Status: Payment Due"], stroke="#e8d37d", fill="#ffffff", title_color="#294c94", text_color="#1e3a8a")
    y = _draw_table(pdf, 16 * mm, height - 108 * mm, 176 * mm, ["Fee Schedule", "Qty", "Rate", "Amount"], _common_rows(items), [94 * mm, 18 * mm, 28 * mm, 36 * mm], header_bg="#eef4ff", header_text="#294c94", line_color="#efe3ad", alt_fill="#fffef7")
    _draw_paragraph(pdf, document.get("notes"), 16 * mm, y - 18, width=56, color="#43557a")
    _draw_paragraph(pdf, document.get("terms"), 16 * mm, y - 52, width=56, color="#43557a")
    right_text = "Accept Quote: Parent signature ____________________" if labels["is_quote"] else document.get("payment_details")
    _draw_paragraph(pdf, right_text, 116 * mm, y - 18, width=38, color="#43557a")
    _draw_totals_box(pdf, 126 * mm, 56 * mm, 66 * mm, _money_rows(document, "Quote Balance" if labels["is_quote"] else "Balance Due"), fill="#ffffff", stroke="#e8d37d", text="#294c94", highlight="#1e3a8a")


def draw_minimalist_black(pdf, width, height, document, items, watermark_label=None):
    labels = _doc_labels(document)
    _draw_watermark(pdf, width, height, watermark_label, "#111111", 62, 90, x=width - 10 * mm, y=height / 2, alpha=0.08)
    pdf.setFillColor(_color("#090909"))
    pdf.setFont("Helvetica-Bold", 46)
    pdf.drawString(16 * mm, height - 26 * mm, labels["heading"])
    pdf.setFont("Helvetica", 10)
    pdf.drawString(16 * mm, height - 34 * mm, _fit(document.get("business_name"), 36))
    pdf.drawString(16 * mm, height - 40 * mm, _fit(document.get("business_email"), 42))
    pdf.setStrokeColor(_color("#111111"))
    pdf.rect(138 * mm, height - 44 * mm, 54 * mm, 28 * mm, fill=0, stroke=1)
    _draw_logo(pdf, document.get("business_logo_url"), 142 * mm, height - 28 * mm, width=14 * mm, height=14 * mm)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(158 * mm, height - 26 * mm, _fit(document.get("document_number"), 16))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(158 * mm, height - 32 * mm, f"Issue {_fmt_date(document.get('issue_date'))}")
    pdf.drawString(158 * mm, height - 38 * mm, f"{labels['date_label']} {_fit(_fmt_date(labels['date_value']), 14)}")
    pdf.line(16 * mm, height - 52 * mm, width - 16 * mm, height - 52 * mm)
    _draw_detail_box(pdf, 16 * mm, height - 60 * mm, 42 * mm, 24 * mm, "Business", [document.get("business_phone"), document.get("business_address")], stroke="#111111", fill="#ffffff", title_color="#666666", text_color="#111111")
    _draw_detail_box(pdf, 62 * mm, height - 60 * mm, 42 * mm, 24 * mm, "Bill To" if not labels["is_quote"] else "Prepared For", [document.get("customer_name"), document.get("customer_address")], stroke="#111111", fill="#ffffff", title_color="#666666", text_color="#111111")
    _draw_detail_box(pdf, 108 * mm, height - 60 * mm, 42 * mm, 24 * mm, "Reference", [document.get("customer_phone") or document.get("customer_email")], stroke="#111111", fill="#ffffff", title_color="#666666", text_color="#111111")
    _draw_detail_box(pdf, 154 * mm, height - 60 * mm, 38 * mm, 24 * mm, "Notes", [document.get("notes")], stroke="#111111", fill="#ffffff", title_color="#666666", text_color="#111111")
    y = _draw_table(pdf, 16 * mm, height - 96 * mm, 130 * mm, ["Item", "Qty", "Unit", "Amount"], _common_rows(items), [66 * mm, 16 * mm, 22 * mm, 26 * mm], header_bg="#ffffff", header_text="#111111", line_color="#d4d4d4", alt_fill="#fafafa")
    _draw_paragraph(pdf, document.get("terms"), 16 * mm, y - 18, width=56, color="#333333")
    pdf.setFillColor(_color("#0b0b0b"))
    pdf.rect(150 * mm, 24 * mm, 42 * mm, 72 * mm, fill=1, stroke=0)
    rows = _money_rows(document, labels["total_label"])
    cursor = 88 * mm
    for idx, (label, value) in enumerate(rows):
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold" if idx == len(rows) - 1 else "Helvetica", 11 if idx == len(rows) - 1 else 9)
        pdf.drawString(154 * mm, cursor, label)
        pdf.drawRightString(188 * mm, cursor, value)
        cursor -= 10 * mm


LAYOUT_DRAWERS = {
    "modern_clean": draw_modern_clean,
    "luxury_gold": draw_luxury_gold,
    "corporate_blue": draw_corporate_blue,
    "retail_receipt": draw_retail_receipt,
    "retail_quote": draw_retail_receipt,
    "restaurant_order": draw_restaurant_order,
    "restaurant_catering": draw_restaurant_order,
    "transport_trip": draw_transport_trip,
    "construction_progress": draw_construction_progress,
    "construction_estimate": draw_construction_progress,
    "medical_statement": draw_medical_statement,
    "medical_plan": draw_medical_statement,
    "school_fees": draw_school_fees,
    "minimal_black": draw_minimalist_black,
}


def generate_document_pdf(document, items, watermark_label=None):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    drawer = LAYOUT_DRAWERS.get(_layout_key(document.get("template_slug")), draw_modern_clean)
    drawer(pdf, width, height, document, items, watermark_label=watermark_label)
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
