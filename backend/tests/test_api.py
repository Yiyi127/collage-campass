import os
import sqlite3
from unittest.mock import patch, MagicMock

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app, read_scorecard_status, ScorecardDatabaseError
from tests.fixtures.sample_schools import build_fixture_db

client = TestClient(app)


def _configure(tmp_path, monkeypatch, api_key="test-anthropic-key"):
    """Point the app at a fresh fixture DB and a non-empty API key."""
    db_path = os.path.join(tmp_path, "scorecard.sqlite")
    build_fixture_db(db_path)
    monkeypatch.setenv("SCORECARD_DB_PATH", db_path)
    if api_key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
    from app.config import get_settings
    get_settings.cache_clear()
    return db_path


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_check_reports_scorecard_data_state(tmp_path, monkeypatch):
    # Fix 4: a deployed instance's data state must be visible without guessing.
    _configure(tmp_path, monkeypatch)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["scorecard_data_year"] == "test-fixture"
    assert body["school_count"] == 3


def test_health_check_reports_degraded_for_a_missing_database(tmp_path, monkeypatch):
    monkeypatch.setenv("SCORECARD_DB_PATH", os.path.join(tmp_path, "nope.sqlite"))
    from app.config import get_settings
    get_settings.cache_clear()
    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["school_count"] == 0


def test_read_scorecard_status_rejects_a_missing_file(tmp_path):
    with pytest.raises(ScorecardDatabaseError, match="not found"):
        read_scorecard_status(os.path.join(tmp_path, "missing.sqlite"))


def test_read_scorecard_status_rejects_an_accidentally_created_empty_db(tmp_path):
    # sqlite3.connect() creates the file, which is exactly the silent-failure
    # mode this check exists to catch.
    path = os.path.join(tmp_path, "empty.sqlite")
    sqlite3.connect(path).close()
    with pytest.raises(ScorecardDatabaseError, match="no `schools` table"):
        read_scorecard_status(path)


def test_read_scorecard_status_rejects_a_zero_row_schools_table(tmp_path):
    path = os.path.join(tmp_path, "norows.sqlite")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schools (unit_id INTEGER)")
    conn.commit()
    conn.close()
    with pytest.raises(ScorecardDatabaseError, match="zero schools"):
        read_scorecard_status(path)


def test_app_startup_fails_loudly_on_a_bad_database_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SCORECARD_DB_PATH", os.path.join(tmp_path, "nope.sqlite"))
    from app.config import get_settings
    get_settings.cache_clear()
    with pytest.raises(ScorecardDatabaseError):
        with TestClient(app):  # entering the context manager runs the lifespan
            pass


def test_app_startup_succeeds_with_a_populated_database(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    with TestClient(app) as started:
        assert started.get("/api/health").json()["status"] == "ok"


def _mock_extraction_response(dream_schools=None, name=None):
    block = MagicMock()
    block.type = "tool_use"
    block.input = {
        "name": name,
        "academics": {"gpa": 3.5, "sat": 1230, "act": None, "ap_scores": []},
        "interests": {"raw_text": "loves programming", "cip_2digit": "11",
                      "cip_4digit_candidates": [], "importance": "preferred"},
        "location": {"home_state": "PA",
                     "geo": {"stated": True, "direction": "near", "importance": "preferred"},
                     "climate": {"stated": False, "preference": None, "importance": "not_mentioned"}},
        "financial": {"needs_aid": False, "stated_budget": None, "family_income": None,
                      "importance": "not_mentioned"},
        "campus_size": {"stated": False, "preference": None, "importance": "not_mentioned"},
        "dream_schools": dream_schools or [], "narrative_context": "practical, hands-on",
    }
    response = MagicMock()
    response.content = [block]
    return response


def _mock_explanation_response(rationales=None):
    import json
    block = MagicMock()
    block.type = "text"
    # Default rationales keyed by Drexel's unit_id (1 in the fixture DB) as a JSON
    # string key, mirroring what the real LLM call returns -- this exercises the
    # int(k)/locked_ids filtering path in explanation.py, not just the template
    # fallback that kicks in when rationales is empty.
    body = {"summary": "A solid list.",
            "rationales": rationales if rationales is not None else
            {"1": "Drexel's co-op program fits your interest in practical, hands-on learning."}}
    block.text = json.dumps(body)
    response = MagicMock()
    response.content = [block]
    return response


def _mock_invalid_extraction_response():
    # A tool_use block whose input fails StudentProfile validation, used to
    # exercise extract_profile's retry-then-raise ProfileExtractionError path.
    block = MagicMock()
    block.type = "tool_use"
    block.input = {"academics": {"gpa": "not-a-number"}}
    response = MagicMock()
    response.content = [block]
    return response


def test_generate_list_returns_bucketed_colleges(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = [_mock_extraction_response(), _mock_explanation_response()]

        response = client.post("/api/generate-list", json={"description": "loves programming, 1230 SAT, PA, wants to stay close to home"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["colleges"]) > 0
    assert body["scoring_version"]
    assert body["scorecard_data_year"] == "test-fixture"
    # Every college must have a non-empty rationale -- Drexel's (unit_id 1) comes
    # from the real LLM-supplied branch, the rest from the template fallback.
    assert all(c["rationale"] for c in body["colleges"])
    drexel = next(c for c in body["colleges"] if c["name"] == "Drexel University")
    assert drexel["rationale"] == "Drexel's co-op program fits your interest in practical, hands-on learning."
    assert body["original_description"] == "loves programming, 1230 SAT, PA, wants to stay close to home"
    # match_score is a 0-100 display figure; run_pipeline's internal
    # total_preference_score is scaled 0-1, so the endpoint must multiply by
    # 100 -- verified live that omitting this rounds every non-trivial score
    # down to 0 or 1, making every school look identical.
    assert all(0 <= c["match_score"] <= 100 for c in body["colleges"])
    assert any(c["match_score"] > 1 for c in body["colleges"])
    # Drexel is in PA, same as the mocked profile's home_state -> 0 miles.
    assert drexel["distance_miles"] == 0


def test_generate_list_reports_student_name_and_headline_when_name_given(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = [
            _mock_extraction_response(name="Jordan"), _mock_explanation_response(),
        ]

        response = client.post("/api/generate-list", json={"description": "Jordan loves programming, 1230 SAT, from PA"})

    body = response.json()
    assert body["student_name"] == "Jordan"
    assert body["profile_headline"] == "loves programming · GPA 3.5 · SAT 1230 · PA"


def test_generate_list_reports_null_student_name_when_none_given(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = [_mock_extraction_response(), _mock_explanation_response()]

        response = client.post("/api/generate-list", json={"description": "loves programming, 1230 SAT, PA"})

    body = response.json()
    assert body["student_name"] is None


def test_generate_list_handles_excluded_dream_school_without_crashing(tmp_path, monkeypatch):
    # `resolve_dream_school` (Task 10) returns {"status": "excluded", "school": None, ...}
    # when a named dream school can't be matched in the DB (or is closed/non-degree-granting).
    # The endpoint must render that as name="Unknown" rather than crashing on `e["school"]["name"]`.
    _configure(tmp_path, monkeypatch)

    dream_schools = [{"name": "Totally Fictional University", "reason": "always dreamed of it"}]

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = [
            _mock_extraction_response(dream_schools=dream_schools),
            _mock_explanation_response(),
        ]

        response = client.post(
            "/api/generate-list",
            json={"description": "loves programming, 1230 SAT, PA, dream school: Totally Fictional University"},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["dream_school_exceptions"]) == 1
    exception = body["dream_school_exceptions"][0]
    assert exception["name"] == "Unknown"
    assert "Totally Fictional University" in exception["reason"]


def test_generate_list_returns_422_when_profile_extraction_fails(tmp_path, monkeypatch):
    # extract_profile (Task 12) retries once on invalid tool_use input, then raises
    # ProfileExtractionError. The endpoint must surface that as a clear HTTP 422,
    # not a 500 or a hang, and must not proceed to call run_pipeline/generate_explanations.
    _configure(tmp_path, monkeypatch)

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = [
            _mock_invalid_extraction_response(),
            _mock_invalid_extraction_response(),
        ]

        response = client.post("/api/generate-list", json={"description": "garbled beyond recognition"})

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]
    assert instance.messages.create.call_count == 2  # both extraction attempts, no explanation call


def test_generate_pdf_returns_pdf_bytes():
    payload = {
        "original_description": "Loves programming, wants hands-on computing programs.",
        "student_summary": "Test summary", "colleges": [
            {"name": "Drexel University", "state": "PA", "bucket": "Target", "confidence": "high",
             "admission_rate": 0.76, "sat_p25": 1160, "sat_p75": 1380, "program_match_type": "exact",
             "net_price": 32000, "affordability_basis": None, "is_dream_school": False,
             "rationale": "Strong co-op program fit.", "match_score": 78, "distance_miles": 12.0,
             "url": "https://drexel.edu"}
        ],
        "dream_school_exceptions": [], "relaxation_notes": [],
        "generated_at": "2026-01-01T00:00:00", "scoring_version": "v1.0", "scorecard_data_year": "test",
    }
    response = client.post("/api/generate-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"



# --- Fix 3: Anthropic API failures must not surface as raw 500s -------------


def _api_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_generate_list_returns_502_when_extraction_hits_an_api_error(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = _api_error()

        response = client.post("/api/generate-list", json={"description": "loves programming"})

    assert response.status_code == 502
    assert "temporarily unavailable" in response.json()["detail"]
    # An API error is not retried -- it is a transport problem, not bad output.
    assert instance.messages.create.call_count == 1


def test_generate_list_still_succeeds_when_explanation_hits_an_api_error(tmp_path, monkeypatch):
    # Explanation failures must degrade to templated rationales, never fail the
    # request -- the list itself is entirely deterministic.
    _configure(tmp_path, monkeypatch)

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = [_mock_extraction_response(), _api_error()]

        response = client.post("/api/generate-list", json={"description": "loves programming"})

    assert response.status_code == 200
    body = response.json()
    assert body["student_summary"]
    assert all(c["rationale"] for c in body["colleges"])


def test_generate_list_reports_a_missing_anthropic_api_key_clearly(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch, api_key=None)

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        response = client.post("/api/generate-list", json={"description": "loves programming"})

    assert response.status_code == 500
    assert response.json()["detail"] == "ANTHROPIC_API_KEY is not configured"
    # The SDK is never even constructed, so its own opaque error can't fire.
    MockAnthropic.assert_not_called()
