import sqlite3
import tempfile
import os
from scripts.refresh_data import build_database

SAMPLE_INSTITUTIONS = [
    {
        "id": 100001, "school.name": "Test State University", "school.state": "PA",
        "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.55,
        "latest.admissions.sat_scores.25th_percentile.critical_reading": 500,
        "latest.admissions.sat_scores.25th_percentile.math": 500,
        "latest.admissions.sat_scores.75th_percentile.critical_reading": 620,
        "latest.admissions.sat_scores.75th_percentile.math": 620,
        "latest.student.size": 8000,
        "latest.cost.avg_net_price.overall": 15000,
        "latest.academics.program_percentage.computer": 0.12,
    }
]
SAMPLE_FIELD_OF_STUDY = [
    {
        "unitid": 100001, "cipcode": "11.0701", "credlev": 3,
        "counts.ipeds_count": 80, "earnings.median": 60000, "debt.median": 21000,
    }
]


def test_build_database_creates_expected_tables_and_rows():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "scorecard.sqlite")
        build_database(SAMPLE_INSTITUTIONS, SAMPLE_FIELD_OF_STUDY, db_path, scorecard_data_year="2023-24")

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT unit_id, name, state, operating, grants_bachelors, admission_rate, "
            "sat_p25, sat_p75, enrollment, net_price_overall FROM schools WHERE unit_id = 100001"
        ).fetchone()
        assert row == (100001, "Test State University", "PA", 1, 1, 0.55, 1000, 1240, 8000, 15000.0)

        cip_row = conn.execute(
            "SELECT cip_2digit, percentage FROM cip2_percentages WHERE unit_id = 100001"
        ).fetchone()
        assert cip_row == ("11", 0.12)

        fos_row = conn.execute(
            "SELECT cip_code, credential_level, graduates, median_earnings, median_debt "
            "FROM field_of_study WHERE unit_id = 100001"
        ).fetchone()
        assert fos_row == ("11.0701", "bachelors", 80, 60000.0, 21000.0)

        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta["scorecard_data_year"] == "2023-24"
        assert "fetched_at" in meta
        conn.close()
