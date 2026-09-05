import tempfile
import os
from tests.fixtures.sample_schools import build_fixture_db
from app.db import get_connection
from app.dream_schools import resolve_dream_school


def _conn(tmp):
    path = os.path.join(tmp, "scorecard.sqlite")
    build_fixture_db(path)
    return get_connection(path)


def test_unmatched_name_is_excluded_with_warning():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Totally Fictional University", None, None)
        assert result["status"] == "excluded"
        assert "Totally Fictional University" in result["reason"]


def test_closed_school_is_excluded():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Closed Institute of Technology", None, None)
        assert result["status"] == "excluded"


def test_valid_school_violating_required_state_is_an_exception():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Massachusetts Institute of Technology", "PA", None)
        assert result["status"] == "exception"
        assert result["school"]["name"] == "Massachusetts Institute of Technology"
        assert "PA" in result["reason"]


def test_valid_school_satisfying_constraints_is_included():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Drexel University", "PA", None)
        assert result["status"] == "included"
        assert result["school"]["name"] == "Drexel University"


# --- Distinct exclusion reasons --------------------------------------------
# "not found", "closed" and "no bachelor's degrees" are three different facts
# and must not share one generic message.


def test_unmatched_name_reason_points_at_the_name_not_at_the_school():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Totally Fictional University", None, None)
        assert result["status"] == "excluded"
        assert "No school matching" in result["reason"]
        assert "spelling" in result["reason"]


def test_closed_school_reason_says_it_is_no_longer_operating():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Closed Institute of Technology", None, None)
        assert result["status"] == "excluded"
        assert "no longer" in result["reason"]
        assert "operating" in result["reason"]
        assert "Closed Institute of Technology" in result["reason"]


def test_non_bachelors_school_reason_says_so_specifically():
    from scripts.refresh_data import build_database
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "assoc.sqlite")
        build_database(
            [{"id": 50, "school.name": "Community College of Somewhere", "school.state": "PA",
              "school.operating": 1, "latest.school.degrees_awarded.predominant": 2,
              "latest.student.size": 9000, "latest.cost.avg_net_price.overall": 8000}],
            [], path, scorecard_data_year="test-fixture",
        )
        conn = get_connection(path)
        result = resolve_dream_school(conn, "Community College of Somewhere", None, None)
        assert result["status"] == "excluded"
        assert "bachelor's degrees" in result["reason"]
        assert "Community College of Somewhere" in result["reason"]


# --- Budget-violation exception path ---------------------------------------


def test_valid_school_violating_required_budget_is_an_exception():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        # Drexel's fixture net price is $32,000, over a hard $25,000 cap.
        result = resolve_dream_school(conn, "Drexel University", None, 25000)
        assert result["status"] == "exception"
        assert result["school"]["name"] == "Drexel University"
        assert "$32,000" in result["reason"]
        assert "$25,000" in result["reason"]


def test_school_within_the_required_budget_is_included():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Drexel University", None, 40000)
        assert result["status"] == "included"


def test_state_violation_is_reported_before_budget_violation():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        # MIT violates both constraints; the state conflict is the one surfaced.
        result = resolve_dream_school(conn, "Massachusetts Institute of Technology", "PA", 1000)
        assert result["status"] == "exception"
        assert "PA" in result["reason"]
