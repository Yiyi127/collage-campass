BASE_WEIGHTS = {"program": 25.0, "geography": 25.0, "affordability": 25.0, "campus_size": 25.0}
IMPORTANCE_MULTIPLIER = {"not_mentioned": 1.0, "default": 1.0, "preferred": 1.4, "required": 1.4}


def compute_weights(active: dict, importances: dict) -> dict:
    raw = {}
    for dim, is_active in active.items():
        if not is_active:
            continue
        multiplier = IMPORTANCE_MULTIPLIER.get(importances.get(dim, "default"), 1.0)
        raw[dim] = BASE_WEIGHTS[dim] * multiplier

    result = {dim: 0.0 for dim in BASE_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return result
    for dim, value in raw.items():
        result[dim] = (value / total) * 100.0
    return result
