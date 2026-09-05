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


def test_ap_score_validates_when_score_is_none():
    """An AP mention with no stated score must not force a fabricated number."""
    tool_input = dict(VALID_TOOL_INPUT)
    tool_input["academics"] = {
        "gpa": 3.5, "sat": 1230, "act": None,
        "ap_scores": [{"subject": "Biology", "score": None}],
    }

    profile = StudentProfile.model_validate(tool_input)

    assert profile.academics.ap_scores[0].subject == "Biology"
    assert profile.academics.ap_scores[0].score is None


def test_ap_score_validates_bare_subject_string():
    """A bare subject-name string (no score object at all) must also validate."""
    tool_input = dict(VALID_TOOL_INPUT)
    tool_input["academics"] = {
        "gpa": 3.5, "sat": 1230, "act": None,
        "ap_scores": ["Biology"],
    }

    profile = StudentProfile.model_validate(tool_input)

    assert profile.academics.ap_scores[0].subject == "Biology"
    assert profile.academics.ap_scores[0].score is None


def test_marine_biology_golden_fixture_validates_against_student_profile():
    """Task 11's approved golden fixture (bare-string ap_scores) must round-trip
    through StudentProfile without raising, since it represents a realistic
    extraction result that run_pipeline already accepts."""
    from tests.test_pipeline_golden import MARINE_BIOLOGY_PROFILE

    profile = StudentProfile.model_validate(MARINE_BIOLOGY_PROFILE)

    assert profile.academics.ap_scores[0].subject == "Biology"
    assert profile.academics.ap_scores[0].score is None


def test_extract_profile_accepts_ap_mention_with_no_score():
    client = MagicMock()
    tool_input = dict(VALID_TOOL_INPUT)
    tool_input["academics"] = {
        "gpa": 3.5, "sat": 1230, "act": None,
        "ap_scores": [{"subject": "Chemistry", "score": None}],
    }
    client.messages.create.return_value = _mock_response(tool_input)

    profile = extract_profile(client, "took AP Chemistry, no score mentioned")

    assert profile.academics.ap_scores[0].subject == "Chemistry"
    assert profile.academics.ap_scores[0].score is None


# --- Anthropic API errors --------------------------------------------------
# A raw API failure (rate limit, overload, auth, connection) is deliberately
# NOT retried and NOT converted into a ProfileExtractionError: it is a
# transport/service problem rather than a malformed-output problem, and the two
# need different HTTP statuses (502 vs 422). The SDK already retries internally.

import anthropic
import httpx


def _api_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_api_error_on_the_first_attempt_propagates_without_retrying():
    client = MagicMock()
    client.messages.create.side_effect = _api_error()

    with pytest.raises(anthropic.APIError):
        extract_profile(client, "some description")

    assert client.messages.create.call_count == 1


def test_api_error_is_not_masked_as_a_profile_extraction_error():
    client = MagicMock()
    client.messages.create.side_effect = _api_error()

    with pytest.raises(anthropic.APIError):
        extract_profile(client, "some description")


def test_api_error_on_the_retry_attempt_propagates_as_an_api_error():
    # First attempt returns malformed output (legitimately retried), the retry
    # then hits the API failure -- the caller must still see an APIError, not a
    # misleading "could not extract a valid profile" message.
    client = MagicMock()
    invalid = {"academics": {"gpa": "not-a-number"}}
    client.messages.create.side_effect = [_mock_response(invalid), _api_error()]

    with pytest.raises(anthropic.APIError):
        extract_profile(client, "some description")

    assert client.messages.create.call_count == 2
