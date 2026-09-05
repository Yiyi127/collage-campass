from io import BytesIO
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from app.pdf.chart import compute_star_positions, RING_RADIUS

PARCHMENT = HexColor("#EDE3C8")
INK_NAVY = HexColor("#1B2A4A")
GOLD_LEAF = HexColor("#B8862E")
BUCKET_COLORS = {"Reach": HexColor("#9B3B26"), "Target": HexColor("#5C6E4A"), "Likely": HexColor("#2E5C55")}

LEFT_MARGIN = 60


def _wrap(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Greedy word wrap against real font metrics."""
    lines: list[str] = []
    current = ""
    for word in (text or "").split():
        candidate = f"{current} {word}".strip()
        if current and stringWidth(candidate, font, size) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_chart(c, colleges, center_x, center_y):
    # The three concentric rings -- same radii the web StarChart draws, so the
    # printed chart and the on-screen chart stay one visual language.
    c.setStrokeColor(INK_NAVY)
    c.setLineWidth(0.5)
    for bucket, radius in RING_RADIUS.items():
        c.circle(center_x, center_y, radius, fill=0, stroke=1)
        c.setFillColor(BUCKET_COLORS[bucket])
        c.setFont("Helvetica-Oblique", 8)
        c.drawCentredString(center_x, center_y + radius + 4, bucket)

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
    text_width = width - 2 * LEFT_MARGIN

    def new_page():
        c.showPage()
        c.setFillColor(PARCHMENT)
        c.rect(0, 0, width, height, fill=1, stroke=0)

    c.setFillColor(PARCHMENT)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    c.setFillColor(INK_NAVY)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 60, "College Compass")

    # Student summary (LLM Call #2's overall narrative), near the top.
    y = height - 88
    c.setFont("Helvetica-Oblique", 10)
    for line in _wrap(response.student_summary, "Helvetica-Oblique", 10, text_width):
        c.drawCentredString(width / 2, y, line)
        y -= 14

    chart_center_y = y - 20 - max(RING_RADIUS.values())
    college_dicts = [
        {"school": {"unit_id": i, "name": entry.name}, "bucket": entry.bucket}
        for i, entry in enumerate(response.colleges)
    ]
    _draw_chart(c, college_dicts, width / 2, chart_center_y)

    y = chart_center_y - max(RING_RADIUS.values()) - 40
    for entry in response.colleges:
        if y < 80:
            new_page()
            y = height - 60
        c.setFillColor(BUCKET_COLORS[entry.bucket])
        c.circle(LEFT_MARGIN, y + 3, 3, fill=1, stroke=0)
        c.setFillColor(INK_NAVY)
        c.setFont("Helvetica", 11)
        star = "* " if entry.is_dream_school else ""
        c.drawString(LEFT_MARGIN + 15, y, f"{star}{entry.name} — {entry.bucket} ({entry.state})")
        y -= 16
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(LEFT_MARGIN + 15, y, entry.rationale[:110])
        y -= 20

    if response.dream_school_exceptions:
        if y < 120:
            new_page()
            y = height - 60
        y -= 10
        c.setFillColor(INK_NAVY)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(LEFT_MARGIN, y, "Dream Schools — Noted Exceptions")
        y -= 20
        for exception in response.dream_school_exceptions:
            if y < 80:
                new_page()
                y = height - 60
            c.setFillColor(GOLD_LEAF)
            c.setFont("Helvetica-Bold", 11)
            c.drawString(LEFT_MARGIN, y, exception.name)
            y -= 14
            c.setFillColor(INK_NAVY)
            c.setFont("Helvetica", 9)
            for line in _wrap(exception.reason, "Helvetica", 9, text_width):
                if y < 60:
                    new_page()
                    y = height - 60
                c.drawString(LEFT_MARGIN, y, line)
                y -= 12
            y -= 8

    c.save()
    return buffer.getvalue()
