from app.scoring.campus_size import campus_size_fit


def test_inactive_when_not_stated():
    score, active = campus_size_fit(8000, False, None, "not_mentioned")
    assert active is False


def test_inactive_when_stated_but_preference_missing():
    # A profile can plausibly have stated=True with preference=None (e.g. the
    # LLM detected campus size was mentioned but couldn't classify it) --
    # this must not KeyError on SIZE_BANDS[None].
    score, active = campus_size_fit(8000, True, None, "preferred")
    assert active is False
    assert score == 0.0


def test_any_school_inside_band_gets_max_score():
    low_end, active1 = campus_size_fit(4900, True, "small", "preferred")
    mid, active2 = campus_size_fit(2500, True, "small", "preferred")
    assert active1 and active2
    assert low_end == mid == 1.0  # both inside [0, 5000), not "closer to midpoint is better"


def test_outside_band_decays_toward_zero():
    just_outside, _ = campus_size_fit(5200, True, "small", "preferred")
    far_outside, _ = campus_size_fit(20000, True, "small", "preferred")
    assert 0 < just_outside < 1.0
    assert far_outside < just_outside


# --- Band edges ------------------------------------------------------------
# The bands are half-open: small [0, 5000), medium [5000, 15000), large
# [15000, inf). These pin down which side of each boundary a school lands on.


def test_lower_band_edge_5000_belongs_to_medium_not_small():
    medium, active_medium = campus_size_fit(5000, True, "medium", "preferred")
    assert active_medium
    assert medium == 1.0
    # Exactly at the edge, "small" is outside the band but the overshoot is
    # zero, so it still scores the band maximum -- the boundary is continuous.
    small, active_small = campus_size_fit(5000, True, "small", "preferred")
    assert active_small
    assert small == 1.0


def test_upper_band_edge_15000_belongs_to_large_not_medium():
    large, active_large = campus_size_fit(15000, True, "large", "preferred")
    assert active_large
    assert large == 1.0
    medium, active_medium = campus_size_fit(15000, True, "medium", "preferred")
    assert active_medium
    assert medium == 1.0  # zero overshoot at the shared boundary


def test_just_past_each_edge_is_strictly_below_the_band_maximum():
    assert campus_size_fit(4999, True, "medium", "preferred")[0] < 1.0
    assert campus_size_fit(15001, True, "medium", "preferred")[0] < 1.0


# --- Unusable enrollment values --------------------------------------------


def test_zero_enrollment_is_treated_as_missing_data():
    score, active = campus_size_fit(0, True, "small", "preferred")
    assert active is False
    assert score == 0.0


def test_negative_enrollment_is_treated_as_missing_data():
    # A negative enrollment is a bad row, not an extremely small school; it must
    # not produce a near-perfect "small campus" score.
    score, active = campus_size_fit(-500, True, "small", "preferred")
    assert active is False
    assert score == 0.0
