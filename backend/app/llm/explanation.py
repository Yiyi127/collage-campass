# backend/app/llm/explanation.py
import json
import anthropic

SYSTEM_PROMPT = (
    "You write grounded explanations for a college list a counselor will hand to a student. "
    "You are given a locked list of schools with real facts (bucket, program match type, etc) "
    "and the student's profile including narrative context (personal descriptors like 'quiet kid'). "
    "Write a 2-3 sentence overall summary and a 2-3 sentence rationale per school, citing only the "
    "facts provided. You may use narrative context to frame why a school could personally suit the "
    "student, but never assert an unverified fact about the school itself (e.g. never claim a school "
    "'has a quiet culture' — that data does not exist). "
    "Respond with ONLY a JSON object: "
    '{"summary": "...", "rationales": {"<unit_id>": "...", ...}}'
)


def _build_user_message(profile, colleges):
    facts = [
        {"unit_id": c["school"]["unit_id"], "name": c["school"]["name"], "state": c["school"]["state"],
         "bucket": c["bucket"], "program_match_type": c["program_match_type"],
         "is_dream_school": c["is_dream_school"]}
        for c in colleges
    ]
    return json.dumps({"student_narrative_context": profile.narrative_context,
                        "student_interests": profile.interests.raw_text, "schools": facts})


def _template_rationale(college):
    return (f"{college['school']['name']} is classified as a {college['bucket']} based on real "
            f"admissions data for your profile.")


def _fallback(colleges):
    summary = "Here is a college list built from your student's real academic profile and stated preferences."
    return summary, {c["school"]["unit_id"]: _template_rationale(c) for c in colleges}


def generate_explanations(client, profile, colleges):
    try:
        response = client.messages.create(
            model="claude-sonnet-5", max_tokens=1024, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(profile, colleges)}],
        )
    except anthropic.APIError:
        # Graceful degradation: the list itself is entirely deterministic, so an
        # unavailable explanation service must never fail the whole request --
        # fall back to the same templated rationales used for malformed output.
        return _fallback(colleges)

    text_block = next((b for b in response.content if b.type == "text"), None)
    locked_ids = {c["school"]["unit_id"] for c in colleges}

    try:
        parsed = json.loads(text_block.text) if text_block else {}
        summary = parsed["summary"]
        rationales = {int(k): v for k, v in parsed["rationales"].items() if int(k) in locked_ids}
        for c in colleges:
            rationales.setdefault(c["school"]["unit_id"], _template_rationale(c))
        return summary, rationales
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, AttributeError):
        return _fallback(colleges)
