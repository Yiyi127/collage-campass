import sqlite3
import tempfile
import os
from unittest.mock import patch, MagicMock
import httpx
import pytest
from scripts.refresh_data import (
    build_database, institution_fields_string, fetch_institutions,
    extract_field_of_study_records, _PROGRAM_PERCENTAGE_TO_CIP2, _normalize_url,
)

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
        "school.school_url": "www.teststate.edu",
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

        url_row = conn.execute("SELECT url FROM schools WHERE unit_id = 100001").fetchone()
        assert url_row == ("https://www.teststate.edu",)

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


# --- Regression guards: the API request must actually ask for every field that
# --- build_database parses. Previously the `fields` string omitted both the
# --- program_percentage.* keys and the net-price income brackets, so on real
# --- data cip2_percentages and net_price_income_* came back empty/NULL.


def test_institution_fields_string_requests_program_percentage_keys():
    fields = institution_fields_string()
    program_keys = [f for f in fields.split(",")
                    if f.startswith("latest.academics.program_percentage.")]
    assert program_keys, "fields must request at least one program_percentage key"
    # Every suffix the parser knows how to map must be requested.
    for suffix in _PROGRAM_PERCENTAGE_TO_CIP2:
        assert f"latest.academics.program_percentage.{suffix}" in program_keys


def test_institution_fields_string_requests_school_url():
    assert "school.school_url" in institution_fields_string().split(",")


def test_normalize_url_adds_a_scheme_when_missing():
    assert _normalize_url("www.drexel.edu") == "https://www.drexel.edu"


def test_normalize_url_leaves_an_existing_scheme_alone():
    assert _normalize_url("http://drexel.edu") == "http://drexel.edu"


def test_normalize_url_returns_none_for_missing_url():
    assert _normalize_url(None) is None
    assert _normalize_url("") is None


def test_institution_fields_string_requests_net_price_income_brackets():
    fields = institution_fields_string()
    income_keys = [f for f in fields.split(",") if ".by_income_level." in f]
    assert income_keys, "fields must request at least one net-price income bracket"
    for bracket in ("0-30000", "30001-48000", "48001-75000", "75001-110000", "110001-plus"):
        assert f"latest.cost.net_price.public.by_income_level.{bracket}" in income_keys
        assert f"latest.cost.net_price.private.by_income_level.{bracket}" in income_keys


def _ok_response(payload):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def test_fetch_institutions_sends_the_full_fields_string():
    payload = {"results": [{"id": 1}], "metadata": {"total": 1}}
    with patch("scripts.refresh_data.httpx.get", return_value=_ok_response(payload)) as mock_get:
        fetch_institutions("fake-key")
    sent_fields = mock_get.call_args.kwargs["params"]["fields"]
    assert "latest.academics.program_percentage." in sent_fields
    assert ".by_income_level." in sent_fields


def test_institution_fields_string_requests_the_nested_field_of_study_array():
    # Field of study is nested per-institution, not a separate endpoint
    # (verified live: /schools/fieldofstudy is a 404 -- the real data lives
    # at latest.programs.cip_4_digit on the main /schools response).
    fields = institution_fields_string()
    assert "latest.programs.cip_4_digit" in fields.split(",")


def test_extract_field_of_study_records_keeps_only_bachelors_and_normalizes_cip():
    institutions = [{
        "id": 212054,
        "latest.programs.cip_4_digit": [
            {
                "code": "5138", "credential": {"level": 3},
                "counts": {"ipeds_awards1": 470, "ipeds_awards2": 470},
                "earnings": {"1_yr": {"overall_median_earnings": 85441}},
            },
            {
                # Not bachelor's -- must be excluded.
                "code": "0109", "credential": {"level": 5},
                "counts": {"ipeds_awards2": 0},
            },
        ],
    }]
    records = extract_field_of_study_records(institutions)
    assert len(records) == 1
    assert records[0] == {
        "unitid": 212054, "cipcode": "51.38", "credlev": 3,
        "counts.ipeds_count": 470, "earnings.median": 85441, "debt.median": None,
    }


def test_extract_field_of_study_records_falls_back_across_earnings_windows():
    institutions = [{
        "id": 1,
        "latest.programs.cip_4_digit": [{
            "code": "1101", "credential": {"level": 3},
            "counts": {"ipeds_awards2": 10},
            # No 1_yr data reported; should fall back to 4_yr.
            "earnings": {"1_yr": {}, "4_yr": {"overall_median_earnings": 72000}},
        }],
    }]
    records = extract_field_of_study_records(institutions)
    assert records[0]["earnings.median"] == 72000


def test_extract_field_of_study_records_handles_missing_programs_array():
    assert extract_field_of_study_records([{"id": 1}]) == []


def _rate_limited_response():
    request = httpx.Request("GET", "https://api.data.gov/")
    resp = MagicMock()
    resp.status_code = 429
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=request, response=httpx.Response(429, request=request)
    )
    return resp


def test_fetch_institutions_retries_on_429_then_succeeds():
    payload = {"results": [{"id": 1}], "metadata": {"total": 1}}
    responses = [_rate_limited_response(), _ok_response(payload)]
    with patch("scripts.refresh_data.time.sleep") as mock_sleep, \
            patch("scripts.refresh_data.httpx.get", side_effect=responses) as mock_get:
        results = fetch_institutions("fake-key")
    assert len(results) == 1
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(1)


def test_fetch_institutions_gives_up_after_three_attempts():
    responses = [_rate_limited_response() for _ in range(3)]
    with patch("scripts.refresh_data.time.sleep"), \
            patch("scripts.refresh_data.httpx.get", side_effect=responses):
        with pytest.raises(httpx.HTTPStatusError):
            fetch_institutions("fake-key")


def test_fetch_institutions_does_not_retry_a_4xx_that_is_not_429():
    request = httpx.Request("GET", "https://api.data.gov/")
    resp = MagicMock()
    resp.status_code = 403
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=request, response=httpx.Response(403, request=request)
    )
    with patch("scripts.refresh_data.httpx.get", return_value=resp) as mock_get:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_institutions("bad-key")
    assert mock_get.call_count == 1


def test_build_database_populates_net_price_income_brackets():
    record = dict(SAMPLE_INSTITUTIONS[0])
    record["latest.cost.net_price.public.by_income_level.0-30000"] = 5000
    record["latest.cost.net_price.private.by_income_level.110001-plus"] = 41000
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "scorecard.sqlite")
        build_database([record], SAMPLE_FIELD_OF_STUDY, db_path, scorecard_data_year="2023-24")
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT net_price_income_0_30000, net_price_income_110001_plus "
            "FROM schools WHERE unit_id = 100001"
        ).fetchone()
        assert row == (5000.0, 41000.0)
        conn.close()
