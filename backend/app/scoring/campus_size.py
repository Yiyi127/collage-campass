SIZE_BANDS = {"small": (0, 5000), "medium": (5000, 15000), "large": (15000, float("inf"))}


def campus_size_fit(enrollment, stated, preference, importance):
    if not stated or importance == "not_mentioned" or enrollment is None:
        return 0.0, False
    lo, hi = SIZE_BANDS[preference]
    if lo <= enrollment < hi:
        return 1.0, True
    band_width = (hi - lo) if hi != float("inf") else 5000
    overshoot = (lo - enrollment) if enrollment < lo else (enrollment - hi)
    return max(0.0, 1 - overshoot / band_width), True
