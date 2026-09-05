# backend/app/llm/profile_extraction.py
from pydantic import ValidationError
from app.schemas import StudentProfile

EXTRACTION_TOOL = {
    "name": "record_student_profile",
    "description": "Record a structured profile extracted from a counselor's free-form description of a student.",
    "input_schema": StudentProfile.model_json_schema(),
}

SYSTEM_PROMPT = (
    "You are extracting a structured profile from a college counselor's free-form "
    "description of a student. Only extract what is stated or clearly implied. "
    "importance fields must be exactly one of: not_mentioned, default, preferred, required — "
    "'required' means the counselor stated it as non-negotiable (e.g. 'must stay in-state'); "
    "a soft mention like 'would be a plus' should be 'default', not 'preferred'. "
    "cip_2digit must be a standard 2-digit CIP code for the student's stated field of interest, "
    "or null if no field of interest is mentioned. Do not invent facts not present in the text. "
    "Call the record_student_profile tool with the extracted profile."
)


class ProfileExtractionError(Exception):
    pass


def _call_and_validate(client, description):
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_student_profile"},
        messages=[{"role": "user", "content": description}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    return StudentProfile.model_validate(tool_use.input)


def extract_profile(client, description: str) -> StudentProfile:
    try:
        return _call_and_validate(client, description)
    except (ValidationError, StopIteration):
        try:
            return _call_and_validate(client, description)
        except (ValidationError, StopIteration) as exc:
            raise ProfileExtractionError(
                "Could not extract a valid student profile after two attempts."
            ) from exc
