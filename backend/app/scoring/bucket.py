def assign_bucket(admission_rate, sat_p25, sat_p75, student_sat):
    has_sat = sat_p25 is not None and sat_p75 is not None and student_sat is not None
    has_rate = admission_rate is not None

    if has_sat and has_rate:
        confidence = "high"
        if admission_rate < 0.20:
            return "Reach", confidence
        if admission_rate < 0.40:
            return ("Reach" if student_sat < sat_p25 else "Target"), confidence
        if admission_rate < 0.60:
            return ("Target" if student_sat < sat_p75 else "Likely"), confidence
        return ("Target" if student_sat < sat_p25 else "Likely"), confidence

    # Deliberate, not a copy of the high-confidence bands above: with no test
    # scores to split the 20-40% and 40-60% bands, the Target band is
    # intentionally widened to 20-50% and Likely starts at 50% -- a coarser
    # signal should hedge toward the middle bucket rather than pretend to the
    # same resolution. Do not "fix" these to 20/40/60.
    if has_rate:
        confidence = "medium"
        if admission_rate < 0.20:
            return "Reach", confidence
        if admission_rate < 0.50:
            return "Target", confidence
        return "Likely", confidence

    return "Target", "low"
