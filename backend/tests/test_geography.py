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
    score, active = geography_fit("PA", "CA", False, "not_mentioned", None, False, "not_mentioned", None, False)
    assert active is False
    assert score == 0.0


def test_geography_fit_handles_state_outside_centroid_table_gracefully():
    # Puerto Rico (and other territories) aren't in STATE_CENTROIDS; the geo
    # sub-signal should be skipped rather than raising a KeyError.
    score, active = geography_fit("PA", "PR", True, "preferred", "near", False, "not_mentioned", None, False)
    assert active is False
    assert score == 0.0


def test_geography_fit_uses_coastal_states_for_ocean_interest():
    # Arizona is warm but not coastal -> should score 0 for a marine-biology student
    score, active = geography_fit(
        "TX", "AZ", False, "not_mentioned", None, True, "preferred", None, is_ocean_related=True
    )
    assert active is True
    assert score == 0.0
    score2, _ = geography_fit(
        "TX", "FL", False, "not_mentioned", None, True, "preferred", None, is_ocean_related=True
    )
    assert score2 == 1.0


# --- Fix 5: a stated "cold" preference must not be scored as if warm was wanted


def test_cold_preference_scores_a_cold_state_higher_than_a_warm_one():
    cold_state, active_cold = geography_fit(
        "PA", "MN", False, "not_mentioned", None, True, "preferred", "cold", False
    )
    warm_state, active_warm = geography_fit(
        "PA", "FL", False, "not_mentioned", None, True, "preferred", "cold", False
    )
    assert active_cold and active_warm
    assert cold_state > warm_state
    assert (cold_state, warm_state) == (1.0, 0.0)


def test_warm_preference_still_scores_warm_states_higher():
    warm_state, _ = geography_fit(
        "PA", "FL", False, "not_mentioned", None, True, "preferred", "warm", False
    )
    cold_state, _ = geography_fit(
        "PA", "MN", False, "not_mentioned", None, True, "preferred", "warm", False
    )
    assert warm_state == 1.0
    assert cold_state == 0.0


def test_climate_stated_without_a_parsed_preference_defaults_to_warm():
    # preference=None (climate mentioned, direction unclassified) keeps the
    # pre-existing warm-oriented behaviour rather than silently inverting.
    score, active = geography_fit(
        "PA", "FL", False, "not_mentioned", None, True, "preferred", None, False
    )
    assert active is True
    assert score == 1.0


def test_cold_preference_does_not_invert_the_coastal_criterion_for_ocean_majors():
    # "Coastal" serves the major, not the temperature preference -- scoring
    # inland higher for a marine-biology student would be plainly wrong.
    coastal, _ = geography_fit(
        "PA", "ME", False, "not_mentioned", None, True, "preferred", "cold", True
    )
    inland, _ = geography_fit(
        "PA", "NE", False, "not_mentioned", None, True, "preferred", "cold", True
    )
    assert coastal == 1.0
    assert inland == 0.0


def test_cold_preference_averages_with_the_distance_sub_signal():
    # Both sub-signals stated -> averaged. MN is far from PA (low distance
    # score) but cold (climate score 1.0), so the result sits strictly between.
    score, active = geography_fit(
        "PA", "MN", True, "preferred", "near", True, "preferred", "cold", False
    )
    assert active is True
    assert 0.0 < score < 1.0
