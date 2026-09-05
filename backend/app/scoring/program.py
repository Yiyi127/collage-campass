def _find_exact(field_of_study, cip_4digit_candidates):
    for rec in field_of_study:
        if rec["cip_code"] in cip_4digit_candidates and rec["credential_level"] == "bachelors":
            return rec
    return None


def program_fit(cip_2digit, cip_4digit_candidates, field_of_study, cip2_percentages,
                 national_median_grad_count, national_median_earnings):
    if not cip_2digit:
        return 0.0, False, "inactive"

    exact = _find_exact(field_of_study, cip_4digit_candidates)
    if exact:
        match_multiplier, match_type = 1.0, "exact"
        grads, earnings = exact.get("graduates"), exact.get("median_earnings")
    else:
        match_multiplier, match_type = 0.6, "related"
        grads, earnings = None, None

    if grads is not None and national_median_grad_count:
        prominence = min(1.0, grads / national_median_grad_count)
    else:
        prominence = min(1.0, cip2_percentages.get(cip_2digit, 0.0) / 0.15)

    if earnings is not None and national_median_earnings:
        outcomes = min(1.0, earnings / national_median_earnings)
    else:
        outcomes = 0.5

    score = match_multiplier * (0.5 * prominence + 0.5 * outcomes)
    return score, True, match_type
