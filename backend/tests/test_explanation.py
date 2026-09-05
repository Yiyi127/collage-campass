# backend/tests/test_explanation.py
from unittest.mock import MagicMock
from app.llm.explanation import generate_explanations, _template_rationale
from app.schemas import StudentProfile

PROFILE = StudentProfile.model_validate({
    "narrative_context": "Wants practical, hands-on programs; not too far from home.",
    "interests": {"raw_text": "loves programming"},
})

COLLEGES = [
    {"school": {"unit_id": 1, "name": "Drexel University", "state": "PA"},
     "bucket": "Target", "confidence": "high", "total_preference_score": 80.0,
     "is_dream_school": False, "program_match_type": "exact", "affordability_basis": None},
]

COLLEGES_TWO = [
    {"school": {"unit_id": 1, "name": "Drexel University", "state": "PA"},
     "bucket": "Target", "confidence": "high", "total_preference_score": 80.0,
     "is_dream_school": False, "program_match_type": "exact", "affordability_basis": None},
    {"school": {"unit_id": 2, "name": "Penn State University", "state": "PA"},
     "bucket": "Likely", "confidence": "high", "total_preference_score": 70.0,
     "is_dream_school": False, "program_match_type": "related", "affordability_basis": None},
]


def _mock_text_response(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_generate_explanations_parses_summary_and_per_school_rationale():
    client = MagicMock()
    client.messages.create.return_value = _mock_text_response(
        '{"summary": "A solid, well-rounded list.", '
        '"rationales": {"1": "Drexel'"'"'s co-op program fits your interest in practical, hands-on learning."}}'
    )

    summary, rationales = generate_explanations(client, PROFILE, COLLEGES)

    assert summary == "A solid, well-rounded list."
    assert rationales[1] == "Drexel's co-op program fits your interest in practical, hands-on learning."


def test_generate_explanations_tolerates_a_markdown_code_fence():
    # Verified live: Claude occasionally wraps its JSON answer in a ```json
    # fence despite being told not to. Unhandled, this used to fail
    # json.loads and silently fall back to the generic template for every
    # school on the list.
    client = MagicMock()
    client.messages.create.return_value = _mock_text_response(
        '```json\n{"summary": "A solid, well-rounded list.", '
        '"rationales": {"1": "Drexel'"'"'s co-op program fits your interest in practical, hands-on learning."}}\n```'
    )

    summary, rationales = generate_explanations(client, PROFILE, COLLEGES)

    assert summary == "A solid, well-rounded list."
    assert rationales[1] == "Drexel's co-op program fits your interest in practical, hands-on learning."


def test_generate_explanations_falls_back_to_template_for_missing_or_malformed_output():
    client = MagicMock()
    client.messages.create.return_value = _mock_text_response("not valid json at all")

    summary, rationales = generate_explanations(client, PROFILE, COLLEGES)

    assert summary  # non-empty fallback summary
    assert "Drexel University" in rationales[1]  # templated fallback mentions the school by name


def test_generate_explanations_drops_hallucinated_unit_id_not_in_locked_list():
    client = MagicMock()
    client.messages.create.return_value = _mock_text_response(
        '{"summary": "A solid list.", '
        '"rationales": {"1": "Drexel is a strong practical fit.", '
        '"999": "This school does not exist in the locked list."}}'
    )

    summary, rationales = generate_explanations(client, PROFILE, COLLEGES)

    assert summary == "A solid list."
    assert rationales == {1: "Drexel is a strong practical fit."}
    assert 999 not in rationales


def test_generate_explanations_backfills_only_the_missing_school_not_the_covered_one():
    client = MagicMock()
    client.messages.create.return_value = _mock_text_response(
        '{"summary": "A balanced list.", '
        '"rationales": {"1": "Drexel'"'"'s co-op program fits your practical, hands-on interests."}}'
    )

    summary, rationales = generate_explanations(client, PROFILE, COLLEGES_TWO)

    assert rationales[1] == "Drexel's co-op program fits your practical, hands-on interests."
    assert rationales[2] == _template_rationale(COLLEGES_TWO[1])


# --- Anthropic API errors --------------------------------------------------
# The list is entirely deterministic, so an unavailable explanation service
# must degrade to templated rationales rather than fail the whole request.

import anthropic
import httpx


def test_generate_explanations_falls_back_to_template_on_api_error():
    client = MagicMock()
    client.messages.create.side_effect = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )

    summary, rationales = generate_explanations(client, PROFILE, COLLEGES_TWO)

    assert summary  # non-empty fallback summary
    assert rationales[1] == _template_rationale(COLLEGES_TWO[0])
    assert rationales[2] == _template_rationale(COLLEGES_TWO[1])


def test_generate_explanations_falls_back_on_a_rate_limit_error():
    client = MagicMock()
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    client.messages.create.side_effect = anthropic.RateLimitError(
        "rate limited", response=httpx.Response(429, request=request), body=None
    )

    summary, rationales = generate_explanations(client, PROFILE, COLLEGES)

    assert summary
    assert "Drexel University" in rationales[1]
