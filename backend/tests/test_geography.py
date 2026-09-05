from app.scoring.geography import (
    haversine_miles, distance_score, climate_score,
    geography_fit, WARM_STATES, COASTAL_STATES,
)


def test_haversine_same_state_is_zero():
    assert haversine_miles("PA", "PA") == 0.0


def test_haversine_pa_to_ca_is_roughly_correct():
    miles = haversine_miles("PA", "CA")
    assert 2000 < miles < 2700  # real great-circle distance is ~2400mi


def test_distance_score_monotonically_decreases_with_distance_when_near():
    close = distance_score(50, "near")
    mid = distance_score(400, "near")
    far = distance_score(1200, "near")
    assert close > mid > far
    assert close == 1.0


def test_distance_score_inverts_for_far_direction():
    assert distance_score(50, "far") < distance_score(1200, "far")


def test_climate_score_warm_states():
    assert climate_score("FL", WARM_STATES) == 1.0
    assert climate_score("MN", WARM_STATES) == 0.0


def test_geography_fit_inactive_when_nothing_stated():
    score, active = geography_fit("PA", "CA", False, "not_mentioned", None, False, "not_mentioned", False)
    assert active is False
    assert score == 0.0


def test_geography_fit_handles_state_outside_centroid_table_gracefully():
    # Puerto Rico (and other territories) aren't in STATE_CENTROIDS; the geo
    # sub-signal should be skipped rather than raising a KeyError.
    score, active = geography_fit("PA", "PR", True, "preferred", "near", False, "not_mentioned", False)
    assert active is False
    assert score == 0.0


def test_geography_fit_uses_coastal_states_for_ocean_interest():
    # Arizona is warm but not coastal -> should score 0 for a marine-biology student
    score, active = geography_fit(
        "TX", "AZ", False, "not_mentioned", None, True, "preferred", is_ocean_related=True
    )
    assert active is True
    assert score == 0.0
    score2, _ = geography_fit(
        "TX", "FL", False, "not_mentioned", None, True, "preferred", is_ocean_related=True
    )
    assert score2 == 1.0
