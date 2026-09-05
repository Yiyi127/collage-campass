NATIONAL_MEDIAN_NET_PRICE = 18500.0
NATIONAL_MEDIAN_NET_PRICE_BY_INCOME = {
    "0-30000": 12000.0, "30001-48000": 14000.0, "48001-75000": 17000.0,
    "75001-110000": 21000.0, "110001-plus": 27000.0,
}


def _bracket_for_income(income: float) -> str:
    if income <= 30000:
        return "0-30000"
    if income <= 48000:
        return "30001-48000"
    if income <= 75000:
        return "48001-75000"
    if income <= 110000:
        return "75001-110000"
    return "110001-plus"


def _band(ratio: float) -> float:
    if ratio <= 1.0:
        return 1.0
    if ratio <= 1.2:
        return 1.0 + (ratio - 1.0) * (0.5 - 1.0) / (1.2 - 1.0)
    return max(0.0, 0.5 - (ratio - 1.2) * 0.5 / 0.8)


def affordability_fit(net_price_overall, net_price_by_income, stated_budget,
                       family_income, needs_aid, importance):
    if stated_budget is not None:
        basis = "stated_budget"
        price, anchor = net_price_overall, stated_budget
    elif family_income is not None:
        basis = "income_bracket"
        bracket = _bracket_for_income(family_income)
        price = net_price_by_income.get(bracket, net_price_overall)
        anchor = NATIONAL_MEDIAN_NET_PRICE_BY_INCOME[bracket]
    elif needs_aid or importance != "not_mentioned":
        basis = "overall_average"
        price, anchor = net_price_overall, NATIONAL_MEDIAN_NET_PRICE
    else:
        return 0.0, False, "inactive"

    if price is None or anchor is None:
        return 0.5, True, basis
    return _band(price / anchor), True, basis
