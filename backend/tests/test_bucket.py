from app.scoring.bucket import assign_bucket


def test_very_selective_school_is_always_reach_even_with_high_sat():
    bucket, confidence = assign_bucket(admission_rate=0.04, sat_p25=1460, sat_p75=1580, student_sat=1560)
    assert bucket == "Reach"
    assert confidence == "high"


def test_moderately_selective_school_never_labeled_likely():
    # 18% would have been Likely under a naive "sat > p75" rule; the banded
    # guardrail must keep it out of Likely entirely
    bucket, _ = assign_bucket(admission_rate=0.30, sat_p25=1300, sat_p75=1450, student_sat=1500)
    assert bucket in ("Reach", "Target")
    assert bucket != "Likely"


def test_high_admit_rate_and_sat_well_above_range_is_likely():
    bucket, confidence = assign_bucket(admission_rate=0.75, sat_p25=1000, sat_p75=1150, student_sat=1300)
    assert bucket == "Likely"
    assert confidence == "high"


def test_test_optional_school_uses_admission_rate_only_with_medium_confidence():
    bucket, confidence = assign_bucket(admission_rate=0.10, sat_p25=None, sat_p75=None, student_sat=1200)
    assert bucket == "Reach"
    assert confidence == "medium"


def test_missing_all_data_defaults_to_target_with_low_confidence():
    bucket, confidence = assign_bucket(admission_rate=None, sat_p25=None, sat_p75=None, student_sat=1200)
    assert bucket == "Target"
    assert confidence == "low"
