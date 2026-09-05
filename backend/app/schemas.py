# backend/app/schemas.py
from typing import Literal, Optional
from pydantic import BaseModel, Field

Importance = Literal["not_mentioned", "default", "preferred", "required"]


class APScore(BaseModel):
    subject: str
    score: int


class Academics(BaseModel):
    gpa: Optional[float] = None
    sat: Optional[int] = None
    act: Optional[int] = None
    ap_scores: list[APScore] = Field(default_factory=list)


class Interests(BaseModel):
    raw_text: str = ""
    cip_2digit: Optional[str] = None
    cip_4digit_candidates: list[str] = Field(default_factory=list)
    importance: Importance = "not_mentioned"


class GeoPreference(BaseModel):
    stated: bool = False
    direction: Optional[Literal["near", "far"]] = None
    importance: Importance = "not_mentioned"


class ClimatePreference(BaseModel):
    stated: bool = False
    preference: Optional[Literal["warm", "cold"]] = None
    importance: Importance = "not_mentioned"


class Location(BaseModel):
    home_state: Optional[str] = None
    geo: GeoPreference = Field(default_factory=GeoPreference)
    climate: ClimatePreference = Field(default_factory=ClimatePreference)


class Financial(BaseModel):
    needs_aid: bool = False
    stated_budget: Optional[float] = None
    family_income: Optional[float] = None
    importance: Importance = "not_mentioned"


class CampusSizePreference(BaseModel):
    stated: bool = False
    preference: Optional[Literal["small", "medium", "large"]] = None
    importance: Importance = "not_mentioned"


class DreamSchool(BaseModel):
    name: str
    reason: Optional[str] = None


class StudentProfile(BaseModel):
    academics: Academics = Field(default_factory=Academics)
    interests: Interests = Field(default_factory=Interests)
    location: Location = Field(default_factory=Location)
    financial: Financial = Field(default_factory=Financial)
    campus_size: CampusSizePreference = Field(default_factory=CampusSizePreference)
    dream_schools: list[DreamSchool] = Field(default_factory=list)
    narrative_context: str = ""


class GenerateListRequest(BaseModel):
    description: str


class CollegeEntry(BaseModel):
    name: str
    state: str
    bucket: str
    confidence: str
    admission_rate: Optional[float]
    sat_p25: Optional[int]
    sat_p75: Optional[int]
    program_match_type: Optional[str]
    net_price: Optional[float]
    affordability_basis: Optional[str]
    is_dream_school: bool
    rationale: str


class DreamSchoolExceptionEntry(BaseModel):
    name: str
    reason: str


class GenerateListResponse(BaseModel):
    student_summary: str
    colleges: list[CollegeEntry]
    dream_school_exceptions: list[DreamSchoolExceptionEntry]
    relaxation_notes: list[str]
    generated_at: str
    scoring_version: str
    scorecard_data_year: str
