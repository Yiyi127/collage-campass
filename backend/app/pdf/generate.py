from io import BytesIO
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from app.pdf.chart import compute_star_positions

PARCHMENT = HexColor("#EDE3C8")
INK_NAVY = HexColor("#1B2A4A")
GOLD_LEAF = HexColor("#B8862E")
BUCKET_COLORS = {"Reach": HexColor("#9B3B26"), "Target": HexColor("#5C6E4A"), "Likely": HexColor("#2E5C55")}


def _draw_chart(c, colleges, center_x, center_y):
    c.setFillColor(GOLD_LEAF)
    c.circle(center_x, center_y, 6, fill=1, stroke=0)
    for pos in compute_star_positions(colleges):
        x, y = center_x + pos["x"], center_y + pos["y"]
        c.setStrokeColor(INK_NAVY)
        c.setLineWidth(0.5)
        c.line(center_x, center_y, x, y)
        c.setFillColor(BUCKET_COLORS[pos["bucket"]])
        c.circle(x, y, 4, fill=1, stroke=0)


def build_pdf(response) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    c.setFillColor(PARCHMENT)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    c.setFillColor(INK_NAVY)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 60, "College Compass")

    college_dicts = [
        {"school": {"unit_id": i, "name": entry.name}, "bucket": entry.bucket}
        for i, entry in enumerate(response.colleges)
    ]
    _draw_chart(c, college_dicts, width / 2, height - 220)

    y = height - 420
    c.setFont("Helvetica", 11)
    for entry in response.colleges:
        c.setFillColor(BUCKET_COLORS[entry.bucket])
        c.circle(60, y + 3, 3, fill=1, stroke=0)
        c.setFillColor(INK_NAVY)
        c.drawString(75, y, f"{entry.name} — {entry.bucket} ({entry.state})")
        y -= 16
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(75, y, entry.rationale[:110])
        c.setFont("Helvetica", 11)
        y -= 20
        if y < 60:
            c.showPage()
            c.setFillColor(PARCHMENT)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            y = height - 60

    c.save()
    return buffer.getvalue()
