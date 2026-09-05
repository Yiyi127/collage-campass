from app.scoring.weighting import compute_weights


def test_all_inactive_gives_all_zero_weights():
    weights = compute_weights(
        {"program": False, "geography": False, "affordability": False, "campus_size": False},
        {},
    )
    assert weights == {"program": 0.0, "geography": 0.0, "affordability": 0.0, "campus_size": 0.0}


def test_only_active_dimensions_get_nonzero_weight_and_sum_to_100():
    weights = compute_weights(
        {"program": True, "geography": True, "affordability": False, "campus_size": False},
        {"program": "default", "geography": "default"},
    )
    assert weights["affordability"] == 0.0
    assert weights["campus_size"] == 0.0
    assert weights["program"] == 50.0
    assert weights["geography"] == 50.0


def test_preferred_dimension_gets_boosted_over_default():
    weights = compute_weights(
        {"program": True, "geography": True, "affordability": False, "campus_size": False},
        {"program": "preferred", "geography": "default"},
    )
    assert weights["program"] > weights["geography"]
    assert abs(sum(weights.values()) - 100.0) < 1e-9


def test_uniform_importance_falls_back_to_equal_base_proportions():
    weights = compute_weights(
        {"program": True, "geography": True, "affordability": True, "campus_size": True},
        {},  # nothing specified -> all default to "default" -> uniform multiplier
    )
    assert weights["program"] == weights["geography"] == weights["affordability"] == weights["campus_size"] == 25.0
