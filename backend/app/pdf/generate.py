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
# Light tints of the bucket colors, blended toward parchment, used to fill the
# chart's three concentric regions so they read as distinct zones rather than
# just thin outlined rings.
BUCKET_LIGHT_COLORS = {
    "Reach": HexColor("#E8CBBF"), "Target": HexColor("#DAE1CF"), "Likely": HexColor("#D0E1DD"),
}
BUCKET_BLURBS = {
    "Reach": "A competitive school — admission is not guaranteed based on this profile.",
    "Target": "A strong, realistic match for this profile.",
    "Likely": "A high probability of admission based on this profile (no school is ever guaranteed).",
}

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


def _draw_legend(c, x, y, width):
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK_NAVY)
    c.drawString(x, y, "What Reach / Target / Likely mean:")
    y -= 16
    for bucket in ("Reach", "Target", "Likely"):
        c.setFillColor(BUCKET_COLORS[bucket])
        c.circle(x + 4, y + 3, 3, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 14, y, f"{bucket}:")
        label_width = stringWidth(f"{bucket}: ", "Helvetica-Bold", 9)
        c.setFont("Helvetica", 9)
        c.setFillColor(INK_NAVY)
        for i, line in enumerate(_wrap(BUCKET_BLURBS[bucket], "Helvetica", 9, width - 14 - label_width)):
            c.drawString(x + 14 + (label_width if i == 0 else 0), y, line)
            y -= 12
        y -= 2
    return y


def _draw_chart(c, colleges, center_x, center_y):
    # Filled concentric bands (largest radius drawn first, smaller on top) so
    # the three buckets read as distinct colored regions, not just thin rings.
    for bucket, radius in RING_RADIUS.items():
        c.setFillColor(BUCKET_LIGHT_COLORS[bucket])
        c.circle(center_x, center_y, radius, fill=1, stroke=0)

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
        c.setFillColor(PARCHMENT)
        c.circle(x, y, 8, fill=1, stroke=0)
        c.setStrokeColor(BUCKET_COLORS[pos["bucket"]])
        c.setLineWidth(1.2)
        c.circle(x, y, 8, fill=0, stroke=1)
        c.setFillColor(BUCKET_COLORS[pos["bucket"]])
        c.setFont("Helvetica-Bold", 8)
        # unit_id is the school's stable 1-based position in the original
        # response.colleges list -- compute_star_positions regroups points
        # by bucket internally, so a loop-position number here would drift
        # from the number printed next to this same school in the section
        # list below (this was a real bug, fixed the same way the web
        # StarChart.vue's point numbers were).
        c.drawCentredString(x, y - 3, str(pos["unit_id"] + 1))


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

    # The counselor's original free-form request, so the printed list is
    # traceable back to what was actually asked for.
    y = height - 84
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(width / 2, y, "Original request")
    y -= 13
    c.setFont("Helvetica-Oblique", 9)
    for line in _wrap(f"“{response.original_description}”", "Helvetica-Oblique", 9, text_width):
        c.drawCentredString(width / 2, y, line)
        y -= 12

    # Student summary (LLM Call #2's overall narrative).
    y -= 10
    c.setFont("Helvetica-Oblique", 10)
    for line in _wrap(response.student_summary, "Helvetica-Oblique", 10, text_width):
        c.drawCentredString(width / 2, y, line)
        y -= 14

    y -= 10
    y = _draw_legend(c, LEFT_MARGIN, y, text_width)

    chart_center_y = y - 20 - max(RING_RADIUS.values())
    college_dicts = [
        {"school": {"unit_id": i, "name": entry.name}, "bucket": entry.bucket}
        for i, entry in enumerate(response.colleges)
    ]
    _draw_chart(c, college_dicts, width / 2, chart_center_y)

    y = chart_center_y - max(RING_RADIUS.values()) - 40
    # Numbered the same way as the chart above: position in the ORIGINAL
    # response.colleges list, not position within its own section -- so
    # "3. Some College" here is always the same school as point "3" on the
    # chart, regardless of how the list below is split into sections.
    numbered = list(enumerate(response.colleges, start=1))
    rationale_width = width - 2 * LEFT_MARGIN - 15
    for bucket in ("Reach", "Target", "Likely"):
        section_items = [(num, entry) for num, entry in numbered if entry.bucket == bucket]
        if not section_items:
            continue

        if y < 100:
            new_page()
            y = height - 60
        c.setFillColor(BUCKET_COLORS[bucket])
        c.setFont("Helvetica-Bold", 14)
        c.drawString(LEFT_MARGIN, y, bucket)
        c.setLineWidth(0.75)
        c.setStrokeColor(BUCKET_COLORS[bucket])
        c.line(LEFT_MARGIN, y - 4, width - LEFT_MARGIN, y - 4)
        y -= 22

        for num, entry in section_items:
            if y < 90:
                new_page()
                y = height - 60
            c.setFillColor(BUCKET_COLORS[entry.bucket])
            c.circle(LEFT_MARGIN, y + 3, 3, fill=1, stroke=0)

            star = "★ " if entry.is_dream_school else ""
            prefix = f"{num}. {star}"
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(INK_NAVY)
            c.drawString(LEFT_MARGIN + 15, y, prefix)
            name_x = LEFT_MARGIN + 15 + stringWidth(prefix, "Helvetica-Bold", 11)
            name_width = stringWidth(entry.name, "Helvetica-Bold", 11)
            if entry.url:
                # A visible cue (gold, underlined) that this is a link, plus
                # the actual clickable annotation over the same rectangle.
                c.setFillColor(GOLD_LEAF)
                c.drawString(name_x, y, entry.name)
                c.setStrokeColor(GOLD_LEAF)
                c.setLineWidth(0.6)
                c.line(name_x, y - 2, name_x + name_width, y - 2)
                c.linkURL(entry.url, (name_x, y - 3, name_x + name_width, y + 9), relative=0, thickness=0)
            else:
                c.setFillColor(INK_NAVY)
                c.drawString(name_x, y, entry.name)
            y -= 14

            c.setFillColor(INK_NAVY)
            c.setFont("Helvetica", 9)
            stats = [f"{entry.state}", f"Match score: {entry.match_score}/100"]
            if entry.distance_miles is not None:
                stats.append(f"{entry.distance_miles:g} mi from home")
            if entry.net_price is not None:
                stats.append(f"${entry.net_price:,.0f}/yr net price")
            c.drawString(LEFT_MARGIN + 15, y, " · ".join(stats))
            y -= 15

            c.setFont("Helvetica-Oblique", 9)
            for line in _wrap(entry.rationale, "Helvetica-Oblique", 9, rationale_width):
                if y < 60:
                    new_page()
                    y = height - 60
                    c.setFont("Helvetica-Oblique", 9)
                c.drawString(LEFT_MARGIN + 15, y, line)
                y -= 12
            y -= 8

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
