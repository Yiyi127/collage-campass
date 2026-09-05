# backend/tests/test_profile_summary.py
from app.profile_summary import build_profile_headline
from app.schemas import Academics, Interests, Location, StudentProfile


def test_build_profile_headline_joins_available_fields():
    profile = StudentProfile(
        academics=Academics(gpa=3.8, sat=1350),
        interests=Interests(raw_text="loves programming"),
        location=Location(home_state="CA"),
    )

    assert build_profile_headline(profile) == "loves programming · GPA 3.8 · SAT 1350 · CA"


def test_build_profile_headline_prefers_sat_over_act_when_both_present():
    profile = StudentProfile(academics=Academics(sat=1350, act=30))

    assert build_profile_headline(profile) == "SAT 1350"


def test_build_profile_headline_falls_back_to_act_when_no_sat():
    profile = StudentProfile(academics=Academics(act=30))

    assert build_profile_headline(profile) == "ACT 30"


def test_build_profile_headline_truncates_long_raw_text():
    long_text = "a " * 40
    profile = StudentProfile(interests=Interests(raw_text=long_text.strip()))

    headline = build_profile_headline(profile)

    assert headline.endswith("…")
    assert len(headline) <= 61


def test_build_profile_headline_empty_profile_is_empty_string():
    assert build_profile_headline(StudentProfile()) == ""
