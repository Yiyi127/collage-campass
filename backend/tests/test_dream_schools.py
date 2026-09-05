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
