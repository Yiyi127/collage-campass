# backend/tests/test_profile_extraction.py
from unittest.mock import MagicMock
import pytest
from app.llm.profile_extraction import extract_profile, ProfileExtractionError
from app.schemas import StudentProfile

VALID_TOOL_INPUT = {
    "academics": {"gpa": 3.5, "sat": 1230, "act": None, "ap_scores": []},
    "interests": {"raw_text": "loves programming", "cip_2digit": "11",
                  "cip_4digit_candidates": [], "importance": "preferred"},
    "location": {"home_state": "PA",
                 "geo": {"stated": True, "direction": "near", "importance": "preferred"},
                 "climate": {"stated": False, "preference": None, "importance": "not_mentioned"}},
    "financial": {"needs_aid": False, "stated_budget": None, "family_income": None,
                  "importance": "not_mentioned"},
    "campus_size": {"stated": False, "preference": None, "importance": "not_mentioned"},
    "dream_schools": [],
    "narrative_context": "practical, hands-on",
}


def _mock_response(tool_input):
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    return response


def test_extract_profile_returns_validated_profile_on_first_try():
    client = MagicMock()
    client.messages.create.return_value = _mock_response(VALID_TOOL_INPUT)

    profile = extract_profile(client, "loves programming, 1230 SAT, wants to stay near home in PA")

    assert isinstance(profile, StudentProfile)
    assert profile.academics.sat == 1230
    assert profile.location.home_state == "PA"


def test_extract_profile_retries_once_on_invalid_output_then_succeeds():
    client = MagicMock()
    invalid = dict(VALID_TOOL_INPUT)
    invalid["academics"] = {"gpa": "not-a-number"}  # invalid type
    client.messages.create.side_effect = [_mock_response(invalid), _mock_response(VALID_TOOL_INPUT)]

    profile = extract_profile(client, "some description")

    assert profile.academics.sat == 1230
    assert client.messages.create.call_count == 2


def test_extract_profile_raises_after_two_failures():
    client = MagicMock()
    invalid = {"academics": {"gpa": "not-a-number"}}
    client.messages.create.side_effect = [_mock_response(invalid), _mock_response(invalid)]

    with pytest.raises(ProfileExtractionError):
        extract_profile(client, "some description")
