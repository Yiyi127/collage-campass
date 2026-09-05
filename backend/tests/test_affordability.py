from app.scoring.affordability import affordability_fit


def test_inactive_when_no_financial_info_given():
    score, active, basis = affordability_fit(20000, {}, None, None, False, "not_mentioned")
    assert active is False
    assert basis == "inactive"


def test_uses_stated_budget_when_given():
    cheap_score, active, basis = affordability_fit(15000, {}, 20000, None, False, "required")
    expensive_score, _, _ = affordability_fit(30000, {}, 20000, None, False, "required")
    assert basis == "stated_budget"
    assert active is True
    assert cheap_score == 1.0
    assert cheap_score > expensive_score


def test_uses_income_bracket_when_no_budget_given():
    score, active, basis = affordability_fit(9000, {"0-30000": 9000}, None, 25000, True, "preferred")
    assert basis == "income_bracket"
    assert active is True
    assert score == 1.0  # below the national median for that bracket


def test_uses_overall_average_when_only_needs_aid_flagged():
    score, active, basis = affordability_fit(10000, {}, None, None, True, "default")
    assert basis == "overall_average"
    assert active is True
    assert score == 1.0  # well below national median net price


def test_lower_price_scores_at_least_as_high_as_higher_price():
    low, _, _ = affordability_fit(12000, {}, None, None, True, "default")
    high, _, _ = affordability_fit(40000, {}, None, None, True, "default")
    assert low >= high
