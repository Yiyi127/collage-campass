import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from app.config import get_settings
from app.db import get_connection
from app.llm.client import get_client
from app.llm.profile_extraction import extract_profile, ProfileExtractionError
from app.llm.explanation import generate_explanations
from app.pdf.generate import build_pdf
from app.pipeline import run_pipeline
from app.schemas import (
    GenerateListRequest, GenerateListResponse, CollegeEntry, DreamSchoolExceptionEntry,
)

app = FastAPI(title="College Compass")

NATIONAL_MEDIANS = {"grad_count": 100, "earnings": 60000}
SCORING_VERSION = "v1.0"


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/generate-list", response_model=GenerateListResponse)
def generate_list(request: GenerateListRequest):
    settings = get_settings()
    client = get_client()
    try:
        profile = extract_profile(client, request.description)
    except ProfileExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    conn = get_connection(settings.scorecard_db_path)
    result = run_pipeline(conn, profile.model_dump(), NATIONAL_MEDIANS)

    summary, rationales = generate_explanations(client, profile, result["colleges"])

    colleges = [
        CollegeEntry(
            name=c["school"]["name"], state=c["school"]["state"], bucket=c["bucket"],
            confidence=c["confidence"], admission_rate=c["school"]["admission_rate"],
            sat_p25=c["school"]["sat_p25"], sat_p75=c["school"]["sat_p75"],
            program_match_type=c["program_match_type"], net_price=c["school"]["net_price_overall"],
            affordability_basis=c["affordability_basis"], is_dream_school=c["is_dream_school"],
            rationale=rationales.get(c["school"]["unit_id"], ""),
        )
        for c in result["colleges"]
    ]
    exceptions = [
        DreamSchoolExceptionEntry(name=e["school"]["name"] if e.get("school") else "Unknown", reason=e["reason"])
        for e in result["dream_school_exceptions"]
    ]
    scorecard_year = conn.execute("SELECT value FROM meta WHERE key = 'scorecard_data_year'").fetchone()[0]

    return GenerateListResponse(
        student_summary=summary, colleges=colleges, dream_school_exceptions=exceptions,
        relaxation_notes=result["relaxation_notes"],
        generated_at=datetime.datetime.utcnow().isoformat(),
        scoring_version=SCORING_VERSION, scorecard_data_year=scorecard_year,
    )


@app.post("/api/generate-pdf")
def generate_pdf(response_body: GenerateListResponse):
    pdf_bytes = build_pdf(response_body)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=college-compass-list.pdf"},
    )
