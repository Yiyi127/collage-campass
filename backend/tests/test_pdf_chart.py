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
