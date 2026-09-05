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


# --- OR-based program eligibility -----------------------------------------
# Per the design spec, program availability is checked at the 4-digit CIP level
# first and falls back to the CIP-2 family. A school qualifies via EITHER a
# bachelor's-level field_of_study row inside the family OR a non-zero
# cip2_percentages share, so a gap in the institution-level program_percentage
# mapping can no longer zero out the candidate pool.

from scripts.refresh_data import build_database

_BASE_SCHOOL = {
    "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
    "latest.admissions.admission_rate.overall": 0.5, "latest.student.size": 6000,
    "latest.cost.avg_net_price.overall": 20000,
}


def _mixed_signal_conn(tmp):
    institutions = [
        # Has a bachelor's field_of_study row in CIP 11, but no cip2_percentages row.
        {**_BASE_SCHOOL, "id": 10, "school.name": "FOS Only University", "school.state": "NY"},
        # Has a cip2_percentages share for CIP 11, but no field_of_study row.
        {**_BASE_SCHOOL, "id": 11, "school.name": "Percentage Only College", "school.state": "NY",
         "latest.academics.program_percentage.computer": 0.09},
        # Neither signal for CIP 11 -- must be excluded.
        {**_BASE_SCHOOL, "id": 12, "school.name": "No Computing College", "school.state": "NY",
         "latest.academics.program_percentage.history": 0.30},
        # A CIP-11 field_of_study row that is master's-level only -- must NOT qualify.
        {**_BASE_SCHOOL, "id": 13, "school.name": "Masters Only Institute", "school.state": "NY"},
        # A CIP-11 field_of_study row with zero graduates -- must NOT qualify.
        {**_BASE_SCHOOL, "id": 14, "school.name": "Zero Graduates College", "school.state": "NY"},
    ]
    field_of_study = [
        {"unitid": 10, "cipcode": "11.0701", "credlev": 3, "counts.ipeds_count": 40,
         "earnings.median": 70000, "debt.median": 20000},
        {"unitid": 12, "cipcode": "54.0101", "credlev": 3, "counts.ipeds_count": 25,
         "earnings.median": 45000, "debt.median": 20000},
        {"unitid": 13, "cipcode": "11.0701", "credlev": 5, "counts.ipeds_count": 60,
         "earnings.median": 90000, "debt.median": 30000},
        {"unitid": 14, "cipcode": "11.0701", "credlev": 3, "counts.ipeds_count": 0,
         "earnings.median": None, "debt.median": None},
    ]
    path = os.path.join(tmp, "mixed.sqlite")
    build_database(institutions, field_of_study, path, scorecard_data_year="test-fixture")
    return get_connection(path)


def test_eligibility_accepts_field_of_study_match_without_cip2_percentage():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _mixed_signal_conn(tmp)
        names = {r["name"] for r in get_eligible_schools(conn, cip_2digit="11")}
        assert "FOS Only University" in names


def test_eligibility_accepts_cip2_percentage_without_field_of_study_match():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _mixed_signal_conn(tmp)
        names = {r["name"] for r in get_eligible_schools(conn, cip_2digit="11")}
        assert "Percentage Only College" in names


def test_eligibility_rejects_schools_with_neither_signal():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _mixed_signal_conn(tmp)
        names = {r["name"] for r in get_eligible_schools(conn, cip_2digit="11")}
        assert "No Computing College" not in names
        assert "Masters Only Institute" not in names  # non-bachelor's credential level
        assert "Zero Graduates College" not in names  # zero graduates on record


def test_eligible_schools_are_ordered_by_unit_id():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _mixed_signal_conn(tmp)
        ids = [r["unit_id"] for r in get_eligible_schools(conn)]
        assert ids == sorted(ids)
