from app.scoring.bucket import assign_bucket


def test_very_selective_school_is_always_reach_even_with_high_sat():
    # Verify that even when student's SAT is well above the 75th percentile,
    # a highly selective school (< 20% admission rate) is always classified as Reach
    bucket, confidence = assign_bucket(admission_rate=0.04, sat_p25=1460, sat_p75=1580, student_sat=1590)
    assert bucket == "Reach"
    assert confidence == "high"


# 20-40% admission rate band tests (has_sat and has_rate)
def test_moderately_selective_school_student_sat_below_p25_is_reach():
    # 20-40% band: student_sat < sat_p25 should return "Reach"
    bucket, confidence = assign_bucket(admission_rate=0.30, sat_p25=1300, sat_p75=1450, student_sat=1250)
    assert bucket == "Reach"
    assert confidence == "high"


def test_moderately_selective_school_student_sat_between_p25_and_p75_is_target():
    # 20-40% band: sat_p25 <= student_sat < sat_p75 should return "Target"
    bucket, confidence = assign_bucket(admission_rate=0.30, sat_p25=1300, sat_p75=1450, student_sat=1380)
    assert bucket == "Target"
    assert confidence == "high"


def test_moderately_selective_school_student_sat_above_p75_is_target():
    # 20-40% band: student_sat >= sat_p75 should return "Target" (not Likely)
    # This test verifies the banded guardrail that keeps moderately selective
    # schools out of Likely even with high SAT
    bucket, confidence = assign_bucket(admission_rate=0.30, sat_p25=1300, sat_p75=1450, student_sat=1500)
    assert bucket == "Target"
    assert confidence == "high"


# 40-60% admission rate band tests (has_sat and has_rate)
def test_selective_school_student_sat_below_p75_is_target():
    # 40-60% band: student_sat < sat_p75 should return "Target"
    bucket, confidence = assign_bucket(admission_rate=0.50, sat_p25=1200, sat_p75=1380, student_sat=1350)
    assert bucket == "Target"
    assert confidence == "high"


def test_selective_school_student_sat_above_p75_is_likely():
    # 40-60% band: student_sat >= sat_p75 should return "Likely"
    bucket, confidence = assign_bucket(admission_rate=0.50, sat_p25=1200, sat_p75=1380, student_sat=1400)
    assert bucket == "Likely"
    assert confidence == "high"


# 60%+ admission rate band (has_sat and has_rate)
def test_high_admit_rate_and_sat_well_above_range_is_likely():
    bucket, confidence = assign_bucket(admission_rate=0.75, sat_p25=1000, sat_p75=1150, student_sat=1300)
    assert bucket == "Likely"
    assert confidence == "high"


# Rate-only tests (no SAT data available)
def test_test_optional_school_very_selective_uses_admission_rate_only_with_medium_confidence():
    # Rate-only, admission_rate < 0.20: expect "Reach" with medium confidence
    bucket, confidence = assign_bucket(admission_rate=0.10, sat_p25=None, sat_p75=None, student_sat=1200)
    assert bucket == "Reach"
    assert confidence == "medium"


def test_test_optional_school_moderately_selective_uses_admission_rate_only_with_medium_confidence():
    # Rate-only, 0.20 <= admission_rate < 0.50: expect "Target" with medium confidence
    bucket, confidence = assign_bucket(admission_rate=0.30, sat_p25=None, sat_p75=None, student_sat=1200)
    assert bucket == "Target"
    assert confidence == "medium"


def test_test_optional_school_high_admit_rate_uses_admission_rate_only_with_medium_confidence():
    # Rate-only, admission_rate >= 0.50: expect "Likely" with medium confidence
    bucket, confidence = assign_bucket(admission_rate=0.60, sat_p25=None, sat_p75=None, student_sat=1200)
    assert bucket == "Likely"
    assert confidence == "medium"


# Fallback test (missing all data)
def test_missing_all_data_defaults_to_target_with_low_confidence():
    bucket, confidence = assign_bucket(admission_rate=None, sat_p25=None, sat_p75=None, student_sat=1200)
    assert bucket == "Target"
    assert confidence == "low"
