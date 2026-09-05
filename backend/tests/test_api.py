from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


import tempfile
import os
from unittest.mock import patch, MagicMock
from tests.fixtures.sample_schools import build_fixture_db


def _mock_extraction_response(dream_schools=None):
    block = MagicMock()
    block.type = "tool_use"
    block.input = {
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
    db_path = os.path.join(tmp_path, "scorecard.sqlite")
    build_fixture_db(db_path)
    monkeypatch.setenv("SCORECARD_DB_PATH", db_path)
    from app.config import get_settings
    get_settings.cache_clear()

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
    get_settings.cache_clear()


def test_generate_list_handles_excluded_dream_school_without_crashing(tmp_path, monkeypatch):
    # `resolve_dream_school` (Task 10) returns {"status": "excluded", "school": None, ...}
    # when a named dream school can't be matched in the DB (or is closed/non-degree-granting).
    # The endpoint must render that as name="Unknown" rather than crashing on `e["school"]["name"]`.
    db_path = os.path.join(tmp_path, "scorecard.sqlite")
    build_fixture_db(db_path)
    monkeypatch.setenv("SCORECARD_DB_PATH", db_path)
    from app.config import get_settings
    get_settings.cache_clear()

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
    get_settings.cache_clear()


def test_generate_list_returns_422_when_profile_extraction_fails(tmp_path, monkeypatch):
    # extract_profile (Task 12) retries once on invalid tool_use input, then raises
    # ProfileExtractionError. The endpoint must surface that as a clear HTTP 422,
    # not a 500 or a hang, and must not proceed to call run_pipeline/generate_explanations.
    db_path = os.path.join(tmp_path, "scorecard.sqlite")
    build_fixture_db(db_path)
    monkeypatch.setenv("SCORECARD_DB_PATH", db_path)
    from app.config import get_settings
    get_settings.cache_clear()

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
    get_settings.cache_clear()


def test_generate_pdf_returns_pdf_bytes():
    payload = {
        "student_summary": "Test summary", "colleges": [
            {"name": "Drexel University", "state": "PA", "bucket": "Target", "confidence": "high",
             "admission_rate": 0.76, "sat_p25": 1160, "sat_p75": 1380, "program_match_type": "exact",
             "net_price": 32000, "affordability_basis": None, "is_dream_school": False,
             "rationale": "Strong co-op program fit."}
        ],
        "dream_school_exceptions": [], "relaxation_notes": [],
        "generated_at": "2026-01-01T00:00:00", "scoring_version": "v1.0", "scorecard_data_year": "test",
    }
    response = client.post("/api/generate-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"

