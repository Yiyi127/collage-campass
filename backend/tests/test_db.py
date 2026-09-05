import tempfile
import os
from tests.fixtures.sample_schools import build_fixture_db
from app.db import (
    get_connection, get_eligible_schools, find_school_by_name,
    get_field_of_study, get_cip2_percentages,
)


def _fresh_conn(tmp):
    path = os.path.join(tmp, "scorecard.sqlite")
    build_fixture_db(path)
    return get_connection(path)


def test_get_eligible_schools_excludes_closed_and_matches_major():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_conn(tmp)
        results = get_eligible_schools(conn, cip_2digit="11", required_state=None, required_budget=None)
        names = {r["name"] for r in results}
        assert "Drexel University" in names
        assert "Massachusetts Institute of Technology" in names
        assert "Closed Institute of Technology" not in names


def test_get_eligible_schools_applies_required_state():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_conn(tmp)
        results = get_eligible_schools(conn, cip_2digit=None, required_state="PA", required_budget=None)
        names = {r["name"] for r in results}
        assert names == {"Drexel University"}


def test_find_school_by_name_fuzzy_matches():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_conn(tmp)
        result = find_school_by_name(conn, "MIT")
        assert result is None  # "MIT" alone shouldn't fuzzy-match without abbreviation handling
        result = find_school_by_name(conn, "Massachusetts Institute of Tech")
        assert result["name"] == "Massachusetts Institute of Technology"


def test_get_field_of_study_and_cip2_percentages():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_conn(tmp)
        fos = get_field_of_study(conn, 1)
        assert fos[0]["cip_code"] == "11.0701"
        assert fos[0]["graduates"] == 210
        pct = get_cip2_percentages(conn, 1)
        assert pct["11"] == 0.14
