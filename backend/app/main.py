import datetime
import os
import sqlite3
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from app.config import get_settings, require_anthropic_api_key, ConfigurationError
from app.db import get_connection
from app.llm.client import get_client
from app.llm.profile_extraction import extract_profile, ProfileExtractionError
from app.llm.explanation import generate_explanations
from app.pdf.generate import build_pdf
from app.pipeline import run_pipeline
from app.schemas import (
    GenerateListRequest, GenerateListResponse, CollegeEntry, DreamSchoolExceptionEntry,
)

NATIONAL_MEDIANS = {"grad_count": 100, "earnings": 60000}
SCORING_VERSION = "v1.0"

AI_UNAVAILABLE_DETAIL = "The AI service is temporarily unavailable. Please try again."


class ScorecardDatabaseError(RuntimeError):
    """The configured scorecard.sqlite is missing, empty, or not a valid snapshot."""


def read_scorecard_status(db_path: str) -> dict:
    """Return {'school_count': int, 'scorecard_data_year': str} for a valid DB.

    `sqlite3.connect` happily *creates* an empty file for a wrong path, so a
    misconfigured SCORECARD_DB_PATH would otherwise stay invisible until a deep
    `OperationalError: no such table` on the first real request.
    """
    if not os.path.exists(db_path):
        raise ScorecardDatabaseError(
            f"Scorecard database not found at {db_path!r}. "
            "Set SCORECARD_DB_PATH, or build it with `python -m scripts.refresh_data`."
        )
    conn = sqlite3.connect(db_path)
    try:
        try:
            count = conn.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
        except sqlite3.OperationalError as exc:
            raise ScorecardDatabaseError(
                f"Scorecard database at {db_path!r} has no `schools` table ({exc}). "
                "It was probably created empty by a wrong SCORECARD_DB_PATH. "
                "Rebuild it with `python -m scripts.refresh_data`."
            ) from exc
        if not count:
            raise ScorecardDatabaseError(
                f"Scorecard database at {db_path!r} contains zero schools. "
                "Rebuild it with `python -m scripts.refresh_data`."
            )
        year_row = conn.execute(
            "SELECT value FROM meta WHERE key = 'scorecard_data_year'"
        ).fetchone()
        return {"school_count": count, "scorecard_data_year": year_row[0] if year_row else None}
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Fail loudly at startup rather than opaquely on the first user request.
    read_scorecard_status(get_settings().scorecard_db_path)
    yield


app = FastAPI(title="College Compass", lifespan=lifespan)

# The frontend is deployed standalone (different origin than this API), and
# there's no cookie-based auth or per-user data here to protect -- every
# request is a stateless description-in, list-out call. Allowing any origin
# is the simplest correct policy for that shape.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    settings = get_settings()
    try:
        status = read_scorecard_status(settings.scorecard_db_path)
    except ScorecardDatabaseError as exc:
        return {"status": "degraded", "detail": str(exc),
                "school_count": 0, "scorecard_data_year": None}
    return {"status": "ok", **status}


@app.post("/api/generate-list", response_model=GenerateListResponse)
def generate_list(request: GenerateListRequest):
    settings = get_settings()
    try:
        require_anthropic_api_key(settings)
    except ConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    client = get_client()
    try:
        profile = extract_profile(client, request.description)
    except ProfileExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except anthropic.APIError:
        raise HTTPException(status_code=502, detail=AI_UNAVAILABLE_DETAIL)

    conn = get_connection(settings.scorecard_db_path)
    result = run_pipeline(conn, profile.model_dump(), NATIONAL_MEDIANS)

    # generate_explanations degrades to templated rationales on an API error, so
    # it needs no error handling here -- an unavailable explanation service must
    # not fail a request whose list is entirely deterministic.
    summary, rationales = generate_explanations(client, profile, result["colleges"])

    colleges = [
        CollegeEntry(
            name=c["school"]["name"], state=c["school"]["state"], bucket=c["bucket"],
            confidence=c["confidence"], admission_rate=c["school"]["admission_rate"],
            sat_p25=c["school"]["sat_p25"], sat_p75=c["school"]["sat_p75"],
            program_match_type=c["program_match_type"], net_price=c["school"]["net_price_overall"],
            affordability_basis=c["affordability_basis"], is_dream_school=c["is_dream_school"],
            rationale=rationales.get(c["school"]["unit_id"], ""),
            match_score=round(c["total_preference_score"] * 100),
            distance_miles=round(c["distance_miles"]) if c["distance_miles"] is not None else None,
            url=c["school"].get("url"),
        )
        for c in result["colleges"]
    ]
    exceptions = [
        DreamSchoolExceptionEntry(name=e["school"]["name"] if e.get("school") else "Unknown", reason=e["reason"])
        for e in result["dream_school_exceptions"]
    ]
    scorecard_year = conn.execute("SELECT value FROM meta WHERE key = 'scorecard_data_year'").fetchone()[0]

    return GenerateListResponse(
        original_description=request.description,
        student_summary=summary, colleges=colleges, dream_school_exceptions=exceptions,
        relaxation_notes=result["relaxation_notes"],
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scoring_version=SCORING_VERSION, scorecard_data_year=scorecard_year,
    )


@app.post("/api/generate-pdf")
def generate_pdf(response_body: GenerateListResponse):
    pdf_bytes = build_pdf(response_body)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=college-compass-list.pdf"},
    )


from fastapi.staticfiles import StaticFiles

_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
