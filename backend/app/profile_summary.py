# backend/app/profile_summary.py
from app.schemas import StudentProfile

RAW_TEXT_MAX_LEN = 60


def build_profile_headline(profile: StudentProfile) -> str:
    """A short, deterministic one-line summary of a profile for display in a
    list of past requests (e.g. "loves programming · GPA 3.8 · SAT 1350 ·
    CA") -- built from already-extracted fields, not a separate LLM call."""
    parts: list[str] = []

    raw_text = profile.interests.raw_text.strip()
    if raw_text:
        if len(raw_text) > RAW_TEXT_MAX_LEN:
            raw_text = raw_text[:RAW_TEXT_MAX_LEN].rstrip() + "…"
        parts.append(raw_text)

    if profile.academics.gpa is not None:
        parts.append(f"GPA {profile.academics.gpa:g}")
    if profile.academics.sat is not None:
        parts.append(f"SAT {profile.academics.sat}")
    elif profile.academics.act is not None:
        parts.append(f"ACT {profile.academics.act}")

    if profile.location.home_state:
        parts.append(profile.location.home_state)

    return " · ".join(parts)
