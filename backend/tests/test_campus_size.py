from app.scoring.campus_size import campus_size_fit


def test_inactive_when_not_stated():
    score, active = campus_size_fit(8000, False, None, "not_mentioned")
    assert active is False


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
