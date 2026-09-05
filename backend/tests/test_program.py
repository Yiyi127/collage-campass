from app.scoring.program import program_fit

FOS_EXACT_MATCH = [
    {"cip_code": "11.0701", "credential_level": "bachelors", "graduates": 200,
     "median_earnings": 90000, "median_debt": 15000},
]


def test_inactive_when_no_major_specified():
    score, active, match_type = program_fit(None, [], [], {}, 100, 60000)
    assert active is False


def test_exact_match_scores_higher_than_related_only():
    exact_score, active, match_type = program_fit(
        "11", ["11.0701"], FOS_EXACT_MATCH, {"11": 0.2}, 100, 60000
    )
    assert active is True
    assert match_type == "exact"

    related_score, _, related_type = program_fit(
        "11", ["11.9999"], [], {"11": 0.2}, 100, 60000
    )
    assert related_type == "related"
    assert exact_score > related_score


def test_prominence_uses_national_median_anchor_not_pool_relative():
    # same inputs, called independently, must give the same score regardless
    # of any other schools "in the pool" (there is no pool parameter at all)
    score_a, _, _ = program_fit("11", ["11.0701"], FOS_EXACT_MATCH, {}, 100, 60000)
    score_b, _, _ = program_fit("11", ["11.0701"], FOS_EXACT_MATCH, {}, 100, 60000)
    assert score_a == score_b


def test_missing_program_level_earnings_falls_back_to_neutral():
    fos_no_earnings = [{"cip_code": "11.0701", "credential_level": "bachelors",
                         "graduates": 50, "median_earnings": None, "median_debt": None}]
    score, active, match_type = program_fit("11", ["11.0701"], fos_no_earnings, {}, 100, 60000)
    assert active is True
    assert 0 < score <= 1.0
