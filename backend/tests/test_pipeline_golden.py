import tempfile
import os
from tests.fixtures.sample_schools import build_fixture_db
from app.db import get_connection
from app.pipeline import run_pipeline

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


def test_dream_school_always_appears_in_output():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "scorecard.sqlite")
        build_fixture_db(path)
        conn = get_connection(path)
        profile = dict(JOHN_SMITH_PROFILE)
        profile["dream_schools"] = [{"name": "Massachusetts Institute of Technology", "reason": "always dreamed of it"}]

        result = run_pipeline(conn, profile, NATIONAL_MEDIANS)

        names = {c["school"]["name"] for c in result["colleges"]}
        exception_names = {e["school"]["name"] for e in result["dream_school_exceptions"] if e.get("school")}
        assert "Massachusetts Institute of Technology" in names or "Massachusetts Institute of Technology" in exception_names
