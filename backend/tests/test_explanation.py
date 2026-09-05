# backend/tests/test_explanation.py
from unittest.mock import MagicMock
from app.llm.explanation import generate_explanations
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


def test_generate_explanations_falls_back_to_template_for_missing_or_malformed_output():
    client = MagicMock()
    client.messages.create.return_value = _mock_text_response("not valid json at all")

    summary, rationales = generate_explanations(client, PROFILE, COLLEGES)

    assert summary  # non-empty fallback summary
    assert "Drexel University" in rationales[1]  # templated fallback mentions the school by name
