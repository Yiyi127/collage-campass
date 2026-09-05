import tempfile
import os
from tests.fixtures.sample_schools import build_fixture_db
from app.db import get_connection
from app.pipeline import run_pipeline
from scripts.refresh_data import build_database

NATIONAL_MEDIANS = {"grad_count": 100, "earnings": 60000}

JOHN_SMITH_PROFILE = {
    "academics": {"gpa": 3.5, "sat": 1230, "act": None, "ap_scores": []},
    "interests": {"raw_text": "loves programming", "cip_2digit": "11",
                  "cip_4digit_candidates": ["11.0701"], "importance": "preferred"},
    "location": {"home_state": "PA",
                 "geo": {"stated": True, "direction": "near", "importance": "preferred"},
                 "climate": {"stated": False, "preference": None, "importance": "not_mentioned"}},
    "financial": {"needs_aid": False, "stated_budget": None, "family_income": None,
                  "importance": "not_mentioned"},
    "campus_size": {"stated": False, "preference": None, "importance": "not_mentioned"},
    "dream_schools": [],
    "narrative_context": "Wants practical, hands-on programs; not too far from home.",
}


def test_john_smith_gets_a_nonempty_bucketed_list():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "scorecard.sqlite")
        build_fixture_db(path)
        conn = get_connection(path)

        result = run_pipeline(conn, JOHN_SMITH_PROFILE, NATIONAL_MEDIANS)

        assert len(result["colleges"]) > 0
        buckets_present = {c["bucket"] for c in result["colleges"]}
        assert buckets_present.issubset({"Reach", "Target", "Likely"})
        # Drexel (PA, in-state, CS program) should score at least as well on
        # geography as MIT (out of state) given a "near home" preference
        by_name = {c["school"]["name"]: c for c in result["colleges"]}
        assert "Drexel University" in by_name


# Second assignment example prompt: a marine-biology-interested student who
# needs financial aid. The fixture DB has no marine-biology field-of-study
# data, so `interests.cip_2digit` is left unset (a plausible LLM output when
# it can't confidently map "marine biology" to a CIP code) -- this test isn't
# exercising the program-fit dimension, it's exercising the climate/ocean-
# keyword geography path and the needs-aid affordability path end-to-end
# without crashing, per the assignment's second worked example.
MARINE_BIOLOGY_PROFILE = {
    "academics": {"gpa": 3.8, "sat": None, "act": 30, "ap_scores": ["Biology"]},
    "interests": {"raw_text": "passionate about marine biology and ocean conservation",
                  "cip_2digit": None, "cip_4digit_candidates": [], "importance": "preferred"},
    "location": {"home_state": "OH",
                 "geo": {"stated": False, "direction": None, "importance": "not_mentioned"},
                 "climate": {"stated": True, "preference": "warm", "importance": "preferred"}},
    "financial": {"needs_aid": True, "stated_budget": None, "family_income": None,
                  "importance": "preferred"},
    "campus_size": {"stated": False, "preference": None, "importance": "not_mentioned"},
    "dream_schools": [],
    "narrative_context": "Needs significant financial aid; drawn to coastal marine biology programs.",
}


def test_marine_biology_financial_aid_student_gets_a_nonempty_bucketed_list():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "scorecard.sqlite")
        build_fixture_db(path)
        conn = get_connection(path)

        result = run_pipeline(conn, MARINE_BIOLOGY_PROFILE, NATIONAL_MEDIANS)

        assert len(result["colleges"]) > 0
        buckets_present = {c["bucket"] for c in result["colleges"]}
        assert buckets_present.issubset({"Reach", "Target", "Likely"})
        for college in result["colleges"]:
            assert college["affordability_basis"] == "overall_average"


def _reach_school(id_, name, net_price):
    return {
        "id": id_, "school.name": name, "school.state": "TX",
        "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.05,
        "latest.student.size": 5000,
        "latest.cost.avg_net_price.overall": net_price,
    }


def test_dream_school_forced_into_output_even_when_truncated_by_score():
    # Build a controlled fixture where the dream school is real, eligible,
    # and lands in the same bucket (Reach) as three other schools that all
    # outscore it on affordability -- so it would be cut by the top-3 rank
    # cutoff if the force-include logic weren't working.
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "scorecard.sqlite")
        institutions = [
            _reach_school(1, "Affordable A", 10000),
            _reach_school(2, "Affordable B", 12000),
            _reach_school(3, "Affordable C", 14000),
            _reach_school(4, "Pricey Dream School", 30000),
        ]
        build_database(institutions, [], path, scorecard_data_year="test-fixture-dream")
        conn = get_connection(path)

        profile = {
            "academics": {"gpa": 3.5, "sat": None, "act": None, "ap_scores": []},
            "interests": {"raw_text": "", "cip_2digit": None, "cip_4digit_candidates": [],
                          "importance": "not_mentioned"},
            "location": {"home_state": "TX",
                         "geo": {"stated": False, "direction": None, "importance": "not_mentioned"},
                         "climate": {"stated": False, "preference": None, "importance": "not_mentioned"}},
            "financial": {"needs_aid": True, "stated_budget": None, "family_income": None,
                          "importance": "required"},
            "campus_size": {"stated": False, "preference": None, "importance": "not_mentioned"},
            "dream_schools": [{"name": "Pricey Dream School", "reason": "always dreamed of it"}],
            "narrative_context": "Needs affordability but has one reach dream school in mind.",
        }

        result = run_pipeline(conn, profile, NATIONAL_MEDIANS)

        reach_names = {c["school"]["name"] for c in result["colleges"] if c["bucket"] == "Reach"}
        assert {"Affordable A", "Affordable B", "Affordable C"}.issubset(reach_names)
        assert "Pricey Dream School" in reach_names
        assert result["dream_school_exceptions"] == []


def test_ties_are_broken_deterministically_by_unit_id():
    # Three identical schools in the same bucket score identically; the ordering
    # must come from an explicit unit_id tie-break, not from SQL row order.
    institutions = [
        {"id": unit_id, "school.name": f"Identical College {unit_id}", "school.state": "PA",
         "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
         "latest.admissions.admission_rate.overall": 0.70,
         "latest.admissions.sat_scores.25th_percentile.critical_reading": 500,
         "latest.admissions.sat_scores.25th_percentile.math": 500,
         "latest.admissions.sat_scores.75th_percentile.critical_reading": 620,
         "latest.admissions.sat_scores.75th_percentile.math": 620,
         "latest.student.size": 8000, "latest.cost.avg_net_price.overall": 20000,
         "latest.academics.program_percentage.computer": 0.10}
        for unit_id in (300, 100, 200)
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ties.sqlite")
        build_database(institutions, [], path, scorecard_data_year="test-fixture")
        conn = get_connection(path)

        result = run_pipeline(conn, JOHN_SMITH_PROFILE, NATIONAL_MEDIANS)

        scores = {c["total_preference_score"] for c in result["colleges"]}
        assert len(scores) == 1, "fixture should produce a genuine tie"
        assert [c["school"]["unit_id"] for c in result["colleges"]] == [100, 200, 300]
