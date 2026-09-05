import math
from app.pdf.chart import compute_star_positions

COLLEGES = [
    {"school": {"unit_id": 1, "name": "A"}, "bucket": "Reach"},
    {"school": {"unit_id": 2, "name": "B"}, "bucket": "Target"},
    {"school": {"unit_id": 3, "name": "C"}, "bucket": "Likely"},
]


def test_reach_schools_are_farther_from_center_than_likely():
    positions = compute_star_positions(COLLEGES)
    by_bucket = {p["bucket"]: p for p in positions}
    reach_dist = math.hypot(by_bucket["Reach"]["x"], by_bucket["Reach"]["y"])
    target_dist = math.hypot(by_bucket["Target"]["x"], by_bucket["Target"]["y"])
    likely_dist = math.hypot(by_bucket["Likely"]["x"], by_bucket["Likely"]["y"])
    assert reach_dist > target_dist > likely_dist


def test_every_college_gets_a_position():
    positions = compute_star_positions(COLLEGES)
    assert {p["unit_id"] for p in positions} == {1, 2, 3}


# --- PDF document rendering ------------------------------------------------
# ReportLab compresses page content streams by default, which makes the drawn
# text unreadable from the raw bytes. Turning compression off for the duration
# of a test lets us assert on what the document actually says.

import pytest
from reportlab import rl_config
from app.pdf.generate import build_pdf
from app.pdf.chart import RING_RADIUS
from app.schemas import GenerateListResponse


@pytest.fixture
def uncompressed_pdf():
    previous = rl_config.pageCompression
    rl_config.pageCompression = 0
    try:
        yield
    finally:
        rl_config.pageCompression = previous


def _response(**overrides):
    payload = {
        "original_description": "Loves programming, wants hands-on computing programs.",
        "student_summary": "A balanced list anchored on hands-on computing programs.",
        "colleges": [
            {"name": "Drexel University", "state": "PA", "bucket": "Target", "confidence": "high",
             "admission_rate": 0.76, "sat_p25": 1160, "sat_p75": 1380, "program_match_type": "exact",
             "net_price": 32000.0, "affordability_basis": None, "is_dream_school": False,
             "rationale": "Strong co-op program fit.", "match_score": 78},
        ],
        "dream_school_exceptions": [], "relaxation_notes": [],
        "generated_at": "2026-01-01T00:00:00", "scoring_version": "v1.0",
        "scorecard_data_year": "test",
    }
    payload.update(overrides)
    return GenerateListResponse.model_validate(payload)


def test_pdf_renders_student_summary(uncompressed_pdf):
    pdf = build_pdf(_response())
    assert b"balanced list anchored" in pdf


def test_pdf_renders_dream_school_exceptions_section(uncompressed_pdf):
    pdf = build_pdf(_response(dream_school_exceptions=[
        {"name": "Massachusetts Institute of Technology",
         "reason": "You named this as a dream school, but it's in MA, which conflicts "
                   "with the requirement to stay in PA."},
    ]))
    assert b"Noted Exceptions" in pdf
    assert b"Massachusetts Institute of Technology" in pdf
    assert b"conflicts" in pdf


def test_pdf_omits_exceptions_heading_when_there_are_none(uncompressed_pdf):
    pdf = build_pdf(_response())
    assert b"Noted Exceptions" not in pdf


def test_pdf_chart_draws_labelled_rings(uncompressed_pdf):
    pdf = build_pdf(_response())
    for label in (b"Reach", b"Target", b"Likely"):
        assert label in pdf


def test_pdf_ring_radii_match_the_shared_chart_geometry():
    # The PDF must draw the same radii the web StarChart does.
    assert RING_RADIUS == {"Reach": 200, "Target": 130, "Likely": 65}
