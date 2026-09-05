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


def _mock_explanation_response():
    import json
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps({"summary": "A solid list.", "rationales": {}})
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
