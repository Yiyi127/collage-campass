# College Compass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build "College Compass" — a webapp where a counselor types a free-form student description and gets back a downloadable, print-ready PDF college list, grounded entirely in real College Scorecard data, with a deterministic ranking core and an LLM used only for language understanding and explanation.

**Architecture:** FastAPI backend reads a pre-built local `scorecard.sqlite` (built by a `refresh-data` CLI against the live College Scorecard API) — no external network calls happen during a live user request except two Anthropic Claude calls (profile extraction, then grounded explanation). All eligibility filtering, Reach/Target/Likely bucketing, and preference ranking are pure, unit-tested Python functions. A Vue 3 + TypeScript frontend renders the result as an SVG "celestial atlas" star chart; the same chart geometry is redrawn as native vector graphics in the PDF via ReportLab. FastAPI serves the built Vue app and the API from one process/deployment.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, `sqlite3` (stdlib), `anthropic` Python SDK, ReportLab, `pytest`. Vue 3, TypeScript, Vite, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-04-college-list-builder-design.md`

## Global Constraints

- No vector DB, embeddings, RAG framework, multi-agent framework, user auth, or persistence of student data beyond a single request/response cycle (from spec's Non-Goals).
- No external network calls at runtime other than the two Anthropic API calls per request — all Scorecard data comes from the local `scorecard.sqlite` built at build/deploy time.
- Every numeric fact and eligibility/bucket/ranking decision is deterministic Python; the LLM never sets a bucket label, invents a number, or reorders the final list (from spec's Core Thesis).
- `importance` is a closed enum: `not_mentioned` / `default` / `preferred` / `required` — never a free-form number from the LLM (spec, StudentProfile section).
- Dimensions with `not_mentioned` importance get weight 0 and are excluded, never defaulted to a full/perfect score (spec, Weighting section).
- All scoring formulas use absolute anchors (fixed distance bands, national median reference figures), never normalization relative to whichever other candidates happen to be in the current request's pool (spec, section 5).
- PDF and web render from one shared response object — never regenerated separately (spec, step [9]).
- Frontend palette/type tokens: `--parchment #EDE3C8`, `--ink-navy #1B2A4A`, `--gold-leaf #B8862E`, `--reach-ember #9B3B26`, `--target-sage #5C6E4A`, `--likely-teal #2E5C55`; `Cormorant` (display), `Spectral` (body), `Space Mono` (data) — all from fonts.googleapis.com (spec, Frontend section).

---

## File Structure

```
backend/
  requirements.txt
  app/
    __init__.py
    config.py                # env var loading
    schemas.py                # StudentProfile + API request/response models
    db.py                      # SQLite query layer over scorecard.sqlite
    scoring/
      __init__.py
      geography.py             # Haversine, state centroids, WARM/COASTAL_STATES, distance decay
      affordability.py          # 3-tier net-price anchoring
      program.py                 # CIP match + prominence + outcomes
      campus_size.py             # enrollment band scoring
      weighting.py                # active-dimension weight renormalization
      bucket.py                    # Reach/Target/Likely + confidence
    dream_schools.py              # fuzzy match + 3-way resolution
    pipeline.py                     # orchestrates candidate retrieval -> bucketing -> scoring -> shortlist
    llm/
      __init__.py
      client.py                     # thin Anthropic client wrapper
      profile_extraction.py          # LLM Call #1 (tool-use, schema-validated, retried once)
      explanation.py                  # LLM Call #2 (grounded narrative, validated against locked facts)
    pdf/
      __init__.py
      chart.py                        # ReportLab vector star-chart drawing (pure geometry + draw)
      generate.py                      # full PDF document assembly
    main.py                            # FastAPI app: routes + static mount
  scripts/
    refresh_data.py                    # CLI: builds scorecard.sqlite from the live Scorecard API
  tests/
    __init__.py
    conftest.py
    fixtures/
      sample_schools.py                # reusable School/FieldOfStudy fixture data
    test_refresh_data.py
    test_db.py
    test_geography.py
    test_affordability.py
    test_program.py
    test_campus_size.py
    test_weighting.py
    test_bucket.py
    test_dream_schools.py
    test_pipeline_golden.py
    test_profile_extraction.py
    test_explanation.py
    test_pdf_chart.py
    test_api.py

frontend/
  package.json
  vite.config.ts
  vitest.config.ts
  tsconfig.json
  index.html
  src/
    main.ts
    App.vue
    api.ts                              # fetch wrappers for backend endpoints
    style/tokens.css                     # color + type design tokens
    chart/
      geometry.ts                         # pure polar-coordinate math (unit tested)
      geometry.test.ts
    components/
      StarChart.vue
      SchoolCard.vue
    views/
      InputView.vue
      ResultsView.vue

Dockerfile / render.yaml                  # single-service deployment config
README.md                                  # setup + API key instructions
```

---

## Task 1: Backend scaffold + health check

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces: `app.config.Settings` (attrs: `anthropic_api_key: str`, `scorecard_db_path: str`), loaded via `app.config.get_settings()`. `app.main.app` — the FastAPI instance later tasks add routes to.

- [ ] **Step 1: Create the backend package and dependency list**

`backend/requirements.txt`:
```
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.6
anthropic>=0.34
reportlab>=4.1
pytest>=8.0
httpx>=0.27
```

`backend/app/__init__.py`: empty file.

`backend/tests/__init__.py`: empty file. This makes `tests` a real package, which is what
makes pytest's rootdir-insertion algorithm walk up to `backend/` and add it to `sys.path` —
required for every later task's `from app.X import ...` and `from tests.fixtures... import ...`
to resolve when running bare `pytest` from `backend/`. Every later task's tests depend on this
file existing; do not skip it.

- [ ] **Step 2: Write `config.py`**

```python
# backend/app/config.py
import os
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    anthropic_api_key: str = ""
    scorecard_db_path: str = "scorecard.sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        scorecard_db_path=os.environ.get("SCORECARD_DB_PATH", "scorecard.sqlite"),
    )
```

- [ ] **Step 3: Write the failing health-check test**

```python
# backend/tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api.py::test_health_check -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.main'` or connection error)

- [ ] **Step 5: Write minimal `main.py`**

```python
# backend/app/main.py
from fastapi import FastAPI

app = FastAPI(title="College Compass")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api.py::test_health_check -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/__init__.py backend/app/config.py backend/app/main.py backend/tests/test_api.py
git commit -m "feat: scaffold FastAPI backend with health check"
```

---

## Task 2: `scorecard.sqlite` schema + refresh-data build logic

**Files:**
- Create: `backend/scripts/refresh_data.py`
- Test: `backend/tests/test_refresh_data.py`

**Interfaces:**
- Produces: `scripts.refresh_data.build_database(institution_records: list[dict], field_of_study_records: list[dict], db_path: str, scorecard_data_year: str) -> None` — pure function, takes already-fetched/parsed API records and writes the SQLite file. `scripts.refresh_data.fetch_institutions(api_key: str) -> list[dict]` and `scripts.refresh_data.fetch_field_of_study(api_key: str) -> list[dict]` — thin live-HTTP functions (not unit tested against the network; verified manually per Step 6).
- SQLite schema written by `build_database`:
  - `schools(unit_id INTEGER PRIMARY KEY, name TEXT, state TEXT, operating INTEGER, grants_bachelors INTEGER, admission_rate REAL, sat_p25 INTEGER, sat_p75 INTEGER, enrollment INTEGER, net_price_overall REAL, net_price_income_0_30000 REAL, net_price_income_30001_48000 REAL, net_price_income_48001_75000 REAL, net_price_income_75001_110000 REAL, net_price_income_110001_plus REAL)`
  - `cip2_percentages(unit_id INTEGER, cip_2digit TEXT, percentage REAL)`
  - `field_of_study(unit_id INTEGER, cip_code TEXT, credential_level TEXT, graduates INTEGER, median_earnings REAL, median_debt REAL)`
  - `meta(key TEXT PRIMARY KEY, value TEXT)` — holds `fetched_at`, `scorecard_data_year`, `schema_version`

- [ ] **Step 1: Write the failing test for `build_database`**

```python
# backend/tests/test_refresh_data.py
import sqlite3
import tempfile
import os
from scripts.refresh_data import build_database

SAMPLE_INSTITUTIONS = [
    {
        "id": 100001, "school.name": "Test State University", "school.state": "PA",
        "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.55,
        "latest.admissions.sat_scores.25th_percentile.critical_reading": 500,
        "latest.admissions.sat_scores.25th_percentile.math": 500,
        "latest.admissions.sat_scores.75th_percentile.critical_reading": 620,
        "latest.admissions.sat_scores.75th_percentile.math": 620,
        "latest.student.size": 8000,
        "latest.cost.avg_net_price.overall": 15000,
        "latest.academics.program_percentage.computer": 0.12,
    }
]
SAMPLE_FIELD_OF_STUDY = [
    {
        "unitid": 100001, "cipcode": "11.0701", "credlev": 3,
        "counts.ipeds_count": 80, "earnings.median": 60000, "debt.median": 21000,
    }
]


def test_build_database_creates_expected_tables_and_rows():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "scorecard.sqlite")
        build_database(SAMPLE_INSTITUTIONS, SAMPLE_FIELD_OF_STUDY, db_path, scorecard_data_year="2023-24")

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT unit_id, name, state, operating, grants_bachelors, admission_rate, "
            "sat_p25, sat_p75, enrollment, net_price_overall FROM schools WHERE unit_id = 100001"
        ).fetchone()
        assert row == (100001, "Test State University", "PA", 1, 1, 0.55, 1000, 1240, 8000, 15000.0)

        cip_row = conn.execute(
            "SELECT cip_2digit, percentage FROM cip2_percentages WHERE unit_id = 100001"
        ).fetchone()
        assert cip_row == ("11", 0.12)

        fos_row = conn.execute(
            "SELECT cip_code, credential_level, graduates, median_earnings, median_debt "
            "FROM field_of_study WHERE unit_id = 100001"
        ).fetchone()
        assert fos_row == ("11.0701", "bachelors", 80, 60000.0, 21000.0)

        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta["scorecard_data_year"] == "2023-24"
        assert "fetched_at" in meta
        conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_refresh_data.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scripts.refresh_data'`)

- [ ] **Step 3: Write `refresh_data.py`**

```python
# backend/scripts/refresh_data.py
import sqlite3
import datetime
import httpx

SCHEMA = """
CREATE TABLE schools (
    unit_id INTEGER PRIMARY KEY, name TEXT, state TEXT,
    operating INTEGER, grants_bachelors INTEGER, admission_rate REAL,
    sat_p25 INTEGER, sat_p75 INTEGER, enrollment INTEGER,
    net_price_overall REAL,
    net_price_income_0_30000 REAL, net_price_income_30001_48000 REAL,
    net_price_income_48001_75000 REAL, net_price_income_75001_110000 REAL,
    net_price_income_110001_plus REAL
);
CREATE TABLE cip2_percentages (unit_id INTEGER, cip_2digit TEXT, percentage REAL);
CREATE TABLE field_of_study (
    unit_id INTEGER, cip_code TEXT, credential_level TEXT,
    graduates INTEGER, median_earnings REAL, median_debt REAL
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""

CREDENTIAL_LEVEL_NAMES = {1: "certificate", 2: "associate", 3: "bachelors", 5: "masters", 6: "doctoral"}


def build_database(institution_records, field_of_study_records, db_path, scorecard_data_year):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    for rec in institution_records:
        sat_p25 = _sum_or_none(rec.get("latest.admissions.sat_scores.25th_percentile.critical_reading"),
                                rec.get("latest.admissions.sat_scores.25th_percentile.math"))
        sat_p75 = _sum_or_none(rec.get("latest.admissions.sat_scores.75th_percentile.critical_reading"),
                                rec.get("latest.admissions.sat_scores.75th_percentile.math"))
        conn.execute(
            "INSERT INTO schools VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec["id"], rec["school.name"], rec["school.state"],
                int(rec.get("school.operating", 1)),
                1 if rec.get("latest.school.degrees_awarded.predominant") == 3 else 0,
                rec.get("latest.admissions.admission_rate.overall"),
                sat_p25, sat_p75,
                rec.get("latest.student.size"),
                rec.get("latest.cost.avg_net_price.overall"),
                rec.get("latest.cost.net_price.public.by_income_level.0-30000")
                or rec.get("latest.cost.net_price.private.by_income_level.0-30000"),
                rec.get("latest.cost.net_price.public.by_income_level.30001-48000")
                or rec.get("latest.cost.net_price.private.by_income_level.30001-48000"),
                rec.get("latest.cost.net_price.public.by_income_level.48001-75000")
                or rec.get("latest.cost.net_price.private.by_income_level.48001-75000"),
                rec.get("latest.cost.net_price.public.by_income_level.75001-110000")
                or rec.get("latest.cost.net_price.private.by_income_level.75001-110000"),
                rec.get("latest.cost.net_price.public.by_income_level.110001-plus")
                or rec.get("latest.cost.net_price.private.by_income_level.110001-plus"),
            ),
        )
        for key, value in rec.items():
            if key.startswith("latest.academics.program_percentage.") and value is not None:
                cip2 = _PROGRAM_PERCENTAGE_TO_CIP2.get(key.rsplit(".", 1)[-1])
                if cip2:
                    conn.execute(
                        "INSERT INTO cip2_percentages VALUES (?,?,?)", (rec["id"], cip2, value)
                    )

    for rec in field_of_study_records:
        conn.execute(
            "INSERT INTO field_of_study VALUES (?,?,?,?,?,?)",
            (
                rec["unitid"], rec["cipcode"],
                CREDENTIAL_LEVEL_NAMES.get(rec.get("credlev"), "unknown"),
                rec.get("counts.ipeds_count"), rec.get("earnings.median"), rec.get("debt.median"),
            ),
        )

    conn.execute("INSERT INTO meta VALUES ('fetched_at', ?)", (datetime.datetime.utcnow().isoformat(),))
    conn.execute("INSERT INTO meta VALUES ('scorecard_data_year', ?)", (scorecard_data_year,))
    conn.execute("INSERT INTO meta VALUES ('schema_version', '1')")
    conn.commit()
    conn.close()


def _sum_or_none(a, b):
    if a is None or b is None:
        return None
    return int(a) + int(b)


# College Scorecard's institution-level program_percentage.* field suffixes map
# to 2-digit CIP family codes. Verify/extend this table against the live API
# response the first time refresh-data is run against real data.
_PROGRAM_PERCENTAGE_TO_CIP2 = {
    "computer": "11", "engineering": "14", "biological": "26",
    "business_marketing": "52", "health": "51", "psychology": "42",
    "visual_performing": "50", "communication": "09", "education": "13",
}


def fetch_institutions(api_key: str) -> list[dict]:
    fields = (
        "id,school.name,school.state,school.operating,"
        "latest.school.degrees_awarded.predominant,"
        "latest.admissions.admission_rate.overall,"
        "latest.admissions.sat_scores.25th_percentile.critical_reading,"
        "latest.admissions.sat_scores.25th_percentile.math,"
        "latest.admissions.sat_scores.75th_percentile.critical_reading,"
        "latest.admissions.sat_scores.75th_percentile.math,"
        "latest.student.size,latest.cost.avg_net_price.overall"
    )
    results = []
    page = 0
    while True:
        resp = httpx.get(
            "https://api.data.gov/ed/collegescorecard/v1/schools",
            params={
                "api_key": api_key, "fields": fields, "per_page": 100, "page": page,
                "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        if len(results) >= data["metadata"]["total"]:
            break
        page += 1
    return results


def fetch_field_of_study(api_key: str) -> list[dict]:
    results = []
    page = 0
    while True:
        resp = httpx.get(
            "https://api.data.gov/ed/collegescorecard/v1/schools/fieldofstudy",
            params={"api_key": api_key, "per_page": 100, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data["results"])
        if len(results) >= data["metadata"]["total"]:
            break
        page += 1
    return results


if __name__ == "__main__":
    import os
    key = os.environ["COLLEGE_SCORECARD_API_KEY"]
    institutions = fetch_institutions(key)
    field_of_study = fetch_field_of_study(key)
    build_database(institutions, field_of_study, "scorecard.sqlite", scorecard_data_year="2023-24")
    print(f"Wrote scorecard.sqlite with {len(institutions)} institutions, {len(field_of_study)} field-of-study rows")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_refresh_data.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/refresh_data.py backend/tests/test_refresh_data.py
git commit -m "feat: add refresh-data CLI that builds versioned scorecard.sqlite"
```

- [ ] **Step 6: Manual verification against the live API (not a unit test)**

Get a free College Scorecard API key at https://collegescorecard.ed.gov/data/api-documentation/
(no credit card required — free signup, key emailed immediately). Then run:

```bash
cd backend && COLLEGE_SCORECARD_API_KEY=<your key> python -m scripts.refresh_data
```

Confirm it completes and prints a row count in the low thousands. Open the resulting
`scorecard.sqlite` with `sqlite3 scorecard.sqlite "SELECT COUNT(*) FROM schools;"` and
spot-check a well-known school's row (e.g. `SELECT * FROM schools WHERE name LIKE '%Pennsylvania State%';`)
looks sane. **If any API field name in `fetch_institutions`/`fetch_field_of_study` doesn't
match the live response** (field names can shift), fix the field list against the actual
response and re-run — this is the checkpoint the design doc flagged as "verify before
building on assumed field names."

---

## Task 3: SQLite query layer

**Files:**
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`
- Create: `backend/tests/fixtures/sample_schools.py`

**Interfaces:**
- Consumes: `scorecard.sqlite` schema from Task 2.
- Produces: `app.db.get_connection(db_path: str) -> sqlite3.Connection`, `app.db.get_eligible_schools(conn, cip_2digit: str | None, required_state: str | None, required_budget: float | None) -> list[dict]`, `app.db.find_school_by_name(conn, name: str) -> dict | None` (fuzzy match), `app.db.get_field_of_study(conn, unit_id: int) -> list[dict]`, `app.db.get_cip2_percentages(conn, unit_id: int) -> dict[str, float]`.

- [ ] **Step 1: Write a shared fixture database**

```python
# backend/tests/fixtures/sample_schools.py
from scripts.refresh_data import build_database

INSTITUTIONS = [
    {
        "id": 1, "school.name": "Drexel University", "school.state": "PA",
        "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.76,
        "latest.admissions.sat_scores.25th_percentile.critical_reading": 570,
        "latest.admissions.sat_scores.25th_percentile.math": 590,
        "latest.admissions.sat_scores.75th_percentile.critical_reading": 680,
        "latest.admissions.sat_scores.75th_percentile.math": 700,
        "latest.student.size": 14000, "latest.cost.avg_net_price.overall": 32000,
        "latest.academics.program_percentage.computer": 0.14,
    },
    {
        "id": 2, "school.name": "Massachusetts Institute of Technology", "school.state": "MA",
        "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.04,
        "latest.admissions.sat_scores.25th_percentile.critical_reading": 730,
        "latest.admissions.sat_scores.25th_percentile.math": 790,
        "latest.admissions.sat_scores.75th_percentile.critical_reading": 780,
        "latest.admissions.sat_scores.75th_percentile.math": 800,
        "latest.student.size": 4600, "latest.cost.avg_net_price.overall": 21000,
        "latest.academics.program_percentage.computer": 0.35,
    },
    {
        "id": 3, "school.name": "Closed Institute of Technology", "school.state": "PA",
        "school.operating": 0, "latest.school.degrees_awarded.predominant": 3,
        "latest.admissions.admission_rate.overall": 0.6,
        "latest.student.size": 1000, "latest.cost.avg_net_price.overall": 20000,
    },
]
FIELD_OF_STUDY = [
    {"unitid": 1, "cipcode": "11.0701", "credlev": 3, "counts.ipeds_count": 210,
     "earnings.median": 68000, "debt.median": 25000},
    {"unitid": 2, "cipcode": "11.0701", "credlev": 3, "counts.ipeds_count": 180,
     "earnings.median": 95000, "debt.median": 12000},
]


def build_fixture_db(path: str):
    build_database(INSTITUTIONS, FIELD_OF_STUDY, path, scorecard_data_year="test-fixture")
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_db.py
import tempfile
import os
from tests.fixtures.sample_schools import build_fixture_db
from app.db import (
    get_connection, get_eligible_schools, find_school_by_name,
    get_field_of_study, get_cip2_percentages,
)


def _fresh_conn(tmp):
    path = os.path.join(tmp, "scorecard.sqlite")
    build_fixture_db(path)
    return get_connection(path)


def test_get_eligible_schools_excludes_closed_and_matches_major():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_conn(tmp)
        results = get_eligible_schools(conn, cip_2digit="11", required_state=None, required_budget=None)
        names = {r["name"] for r in results}
        assert "Drexel University" in names
        assert "Massachusetts Institute of Technology" in names
        assert "Closed Institute of Technology" not in names


def test_get_eligible_schools_applies_required_state():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_conn(tmp)
        results = get_eligible_schools(conn, cip_2digit=None, required_state="PA", required_budget=None)
        names = {r["name"] for r in results}
        assert names == {"Drexel University"}


def test_find_school_by_name_fuzzy_matches():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_conn(tmp)
        result = find_school_by_name(conn, "MIT")
        assert result is None  # "MIT" alone shouldn't fuzzy-match without abbreviation handling
        result = find_school_by_name(conn, "Massachusetts Institute of Tech")
        assert result["name"] == "Massachusetts Institute of Technology"


def test_get_field_of_study_and_cip2_percentages():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _fresh_conn(tmp)
        fos = get_field_of_study(conn, 1)
        assert fos[0]["cip_code"] == "11.0701"
        assert fos[0]["graduates"] == 210
        pct = get_cip2_percentages(conn, 1)
        assert pct["11"] == 0.14
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_db.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.db'`)

- [ ] **Step 4: Write `db.py`**

```python
# backend/app/db.py
import sqlite3
import difflib


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_eligible_schools(conn, cip_2digit=None, required_state=None, required_budget=None):
    query = "SELECT * FROM schools WHERE operating = 1 AND grants_bachelors = 1"
    params = []
    if required_state:
        query += " AND state = ?"
        params.append(required_state)
    if required_budget is not None:
        query += " AND (net_price_overall IS NULL OR net_price_overall <= ?)"
        params.append(required_budget)
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    if cip_2digit:
        eligible_ids = {
            r["unit_id"] for r in conn.execute(
                "SELECT DISTINCT unit_id FROM cip2_percentages WHERE cip_2digit = ? AND percentage > 0",
                (cip_2digit,),
            ).fetchall()
        }
        rows = [r for r in rows if r["unit_id"] in eligible_ids]
    return rows


def find_school_by_name(conn, name: str, cutoff: float = 0.75):
    all_names = [r["name"] for r in conn.execute("SELECT name FROM schools").fetchall()]
    matches = difflib.get_close_matches(name, all_names, n=1, cutoff=cutoff)
    if not matches:
        return None
    row = conn.execute("SELECT * FROM schools WHERE name = ?", (matches[0],)).fetchone()
    return dict(row) if row else None


def get_field_of_study(conn, unit_id: int):
    rows = conn.execute(
        "SELECT cip_code, credential_level, graduates, median_earnings, median_debt "
        "FROM field_of_study WHERE unit_id = ?", (unit_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_cip2_percentages(conn, unit_id: int):
    rows = conn.execute(
        "SELECT cip_2digit, percentage FROM cip2_percentages WHERE unit_id = ?", (unit_id,)
    ).fetchall()
    return {r["cip_2digit"]: r["percentage"] for r in rows}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py backend/tests/fixtures/
git commit -m "feat: add scorecard.sqlite query layer"
```

---

## Task 4: Geography scoring

**Files:**
- Create: `backend/app/scoring/__init__.py` (empty)
- Create: `backend/app/scoring/geography.py`
- Test: `backend/tests/test_geography.py`

**Interfaces:**
- Produces: `haversine_miles(state_a: str, state_b: str) -> float`, `distance_score(miles: float, direction: str) -> float`, `climate_score(state: str, state_set: set[str]) -> float`, `WARM_STATES: set[str]`, `COASTAL_STATES: set[str]`, `geography_fit(home_state: str, school_state: str, geo_stated: bool, geo_importance: str, geo_direction: str | None, climate_stated: bool, climate_importance: str, is_ocean_related: bool) -> tuple[float, bool]` (score, is_active).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_geography.py
from app.scoring.geography import (
    haversine_miles, distance_score, climate_score,
    geography_fit, WARM_STATES, COASTAL_STATES,
)


def test_haversine_same_state_is_zero():
    assert haversine_miles("PA", "PA") == 0.0


def test_haversine_pa_to_ca_is_roughly_correct():
    miles = haversine_miles("PA", "CA")
    assert 2000 < miles < 2700  # real great-circle distance is ~2400mi


def test_distance_score_monotonically_decreases_with_distance_when_near():
    close = distance_score(50, "near")
    mid = distance_score(400, "near")
    far = distance_score(1200, "near")
    assert close > mid > far
    assert close == 1.0


def test_distance_score_inverts_for_far_direction():
    assert distance_score(50, "far") < distance_score(1200, "far")


def test_climate_score_warm_states():
    assert climate_score("FL", WARM_STATES) == 1.0
    assert climate_score("MN", WARM_STATES) == 0.0


def test_geography_fit_inactive_when_nothing_stated():
    score, active = geography_fit("PA", "CA", False, "not_mentioned", None, False, "not_mentioned", False)
    assert active is False
    assert score == 0.0


def test_geography_fit_uses_coastal_states_for_ocean_interest():
    # Arizona is warm but not coastal -> should score 0 for a marine-biology student
    score, active = geography_fit(
        "TX", "AZ", False, "not_mentioned", None, True, "preferred", is_ocean_related=True
    )
    assert active is True
    assert score == 0.0
    score2, _ = geography_fit(
        "TX", "FL", False, "not_mentioned", None, True, "preferred", is_ocean_related=True
    )
    assert score2 == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_geography.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.scoring'`)

- [ ] **Step 3: Write `geography.py`**

```python
# backend/app/scoring/geography.py
import math

STATE_CENTROIDS = {
    "AL": (32.806671, -86.791130), "AK": (61.370716, -152.404419),
    "AZ": (33.729759, -111.431221), "AR": (34.969704, -92.373123),
    "CA": (36.116203, -119.681564), "CO": (39.059811, -105.311104),
    "CT": (41.597782, -72.755371), "DE": (39.318523, -75.507141),
    "FL": (27.766279, -81.686783), "GA": (33.040619, -83.643074),
    "HI": (21.094318, -157.498337), "ID": (44.240459, -114.478828),
    "IL": (40.349457, -88.986137), "IN": (39.849426, -86.258278),
    "IA": (42.011539, -93.210526), "KS": (38.526600, -96.726486),
    "KY": (37.668140, -84.670067), "LA": (31.169546, -91.867805),
    "ME": (44.693947, -69.381927), "MD": (39.063946, -76.802101),
    "MA": (42.230171, -71.530106), "MI": (43.326618, -84.536095),
    "MN": (45.694454, -93.900192), "MS": (32.741646, -89.678696),
    "MO": (38.456085, -92.288368), "MT": (46.921925, -110.454353),
    "NE": (41.125370, -98.268082), "NV": (38.313515, -117.055374),
    "NH": (43.452492, -71.563896), "NJ": (40.298904, -74.521011),
    "NM": (34.840515, -106.248482), "NY": (42.165726, -74.948051),
    "NC": (35.630066, -79.806419), "ND": (47.528912, -99.784012),
    "OH": (40.388783, -82.764915), "OK": (35.565342, -96.928917),
    "OR": (44.572021, -122.070938), "PA": (40.590752, -77.209755),
    "RI": (41.680893, -71.511780), "SC": (33.856892, -80.945007),
    "SD": (44.299782, -99.438828), "TN": (35.747845, -86.692345),
    "TX": (31.054487, -97.563461), "UT": (40.150032, -111.862434),
    "VT": (44.045876, -72.710686), "VA": (37.769337, -78.169968),
    "WA": (47.400902, -121.490494), "WV": (38.491226, -80.954453),
    "WI": (44.268543, -89.616508), "WY": (42.755966, -107.302490),
    "DC": (38.897438, -77.026817),
}

WARM_STATES = {"FL", "GA", "SC", "AL", "MS", "LA", "TX", "AZ", "CA", "HI", "NM"}
COASTAL_STATES = {
    "ME", "NH", "MA", "RI", "CT", "NY", "NJ", "DE", "MD", "VA", "NC", "SC",
    "GA", "FL", "AL", "MS", "LA", "TX", "CA", "OR", "WA", "AK", "HI",
}


def haversine_miles(state_a: str, state_b: str) -> float:
    if state_a == state_b:
        return 0.0
    lat1, lon1 = STATE_CENTROIDS[state_a]
    lat2, lon2 = STATE_CENTROIDS[state_b]
    r = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _near_score(miles: float) -> float:
    if miles <= 100:
        return 1.0
    if miles <= 300:
        return 1.0 + (miles - 100) * (0.7 - 1.0) / (300 - 100)
    if miles <= 600:
        return 0.7 + (miles - 300) * (0.4 - 0.7) / (600 - 300)
    if miles <= 1000:
        return 0.4 + (miles - 600) * (0.15 - 0.4) / (1000 - 600)
    return max(0.0, 0.15 - (miles - 1000) * 0.15 / 500)


def distance_score(miles: float, direction: str = "near") -> float:
    near = _near_score(miles)
    return near if direction == "near" else 1.0 - near


def climate_score(state: str, state_set: set) -> float:
    return 1.0 if state in state_set else 0.0


def geography_fit(home_state, school_state, geo_stated, geo_importance, geo_direction,
                   climate_stated, climate_importance, is_ocean_related):
    scores = []
    if geo_stated and geo_importance != "not_mentioned":
        scores.append(distance_score(haversine_miles(home_state, school_state), geo_direction or "near"))
    if climate_stated and climate_importance != "not_mentioned":
        state_set = COASTAL_STATES if is_ocean_related else WARM_STATES
        scores.append(climate_score(school_state, state_set))
    if not scores:
        return 0.0, False
    return sum(scores) / len(scores), True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_geography.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/scoring/__init__.py backend/app/scoring/geography.py backend/tests/test_geography.py
git commit -m "feat: add deterministic geography scoring"
```

---

## Task 5: Affordability scoring

**Files:**
- Create: `backend/app/scoring/affordability.py`
- Test: `backend/tests/test_affordability.py`

**Interfaces:**
- Produces: `affordability_fit(net_price_overall: float | None, net_price_by_income: dict[str, float], stated_budget: float | None, family_income: float | None, needs_aid: bool, importance: str) -> tuple[float, bool, str]` (score, is_active, basis).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_affordability.py
from app.scoring.affordability import affordability_fit


def test_inactive_when_no_financial_info_given():
    score, active, basis = affordability_fit(20000, {}, None, None, False, "not_mentioned")
    assert active is False
    assert basis == "inactive"


def test_uses_stated_budget_when_given():
    cheap_score, active, basis = affordability_fit(15000, {}, 20000, None, False, "required")
    expensive_score, _, _ = affordability_fit(30000, {}, 20000, None, False, "required")
    assert basis == "stated_budget"
    assert active is True
    assert cheap_score == 1.0
    assert cheap_score > expensive_score


def test_uses_income_bracket_when_no_budget_given():
    score, active, basis = affordability_fit(9000, {"0-30000": 9000}, None, 25000, True, "preferred")
    assert basis == "income_bracket"
    assert active is True
    assert score == 1.0  # below the national median for that bracket


def test_uses_overall_average_when_only_needs_aid_flagged():
    score, active, basis = affordability_fit(10000, {}, None, None, True, "default")
    assert basis == "overall_average"
    assert active is True
    assert score == 1.0  # well below national median net price


def test_lower_price_scores_at_least_as_high_as_higher_price():
    low, _, _ = affordability_fit(12000, {}, None, None, True, "default")
    high, _, _ = affordability_fit(40000, {}, None, None, True, "default")
    assert low >= high
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_affordability.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Write `affordability.py`**

```python
# backend/app/scoring/affordability.py
NATIONAL_MEDIAN_NET_PRICE = 18500.0
NATIONAL_MEDIAN_NET_PRICE_BY_INCOME = {
    "0-30000": 12000.0, "30001-48000": 14000.0, "48001-75000": 17000.0,
    "75001-110000": 21000.0, "110001-plus": 27000.0,
}


def _bracket_for_income(income: float) -> str:
    if income <= 30000:
        return "0-30000"
    if income <= 48000:
        return "30001-48000"
    if income <= 75000:
        return "48001-75000"
    if income <= 110000:
        return "75001-110000"
    return "110001-plus"


def _band(ratio: float) -> float:
    if ratio <= 1.0:
        return 1.0
    if ratio <= 1.2:
        return 1.0 + (ratio - 1.0) * (0.5 - 1.0) / (1.2 - 1.0)
    return max(0.0, 0.5 - (ratio - 1.2) * 0.5 / 0.8)


def affordability_fit(net_price_overall, net_price_by_income, stated_budget,
                       family_income, needs_aid, importance):
    if stated_budget is not None:
        basis = "stated_budget"
        price, anchor = net_price_overall, stated_budget
    elif family_income is not None:
        basis = "income_bracket"
        bracket = _bracket_for_income(family_income)
        price = net_price_by_income.get(bracket, net_price_overall)
        anchor = NATIONAL_MEDIAN_NET_PRICE_BY_INCOME[bracket]
    elif needs_aid or importance != "not_mentioned":
        basis = "overall_average"
        price, anchor = net_price_overall, NATIONAL_MEDIAN_NET_PRICE
    else:
        return 0.0, False, "inactive"

    if price is None or anchor is None:
        return 0.5, True, basis
    return _band(price / anchor), True, basis
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_affordability.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/scoring/affordability.py backend/tests/test_affordability.py
git commit -m "feat: add deterministic affordability scoring"
```

---

## Task 6: Program fit scoring

**Files:**
- Create: `backend/app/scoring/program.py`
- Test: `backend/tests/test_program.py`

**Interfaces:**
- Consumes: `get_field_of_study`/`get_cip2_percentages` row shapes from Task 3.
- Produces: `program_fit(cip_2digit: str | None, cip_4digit_candidates: list[str], field_of_study: list[dict], cip2_percentages: dict[str, float], national_median_grad_count: float, national_median_earnings: float) -> tuple[float, bool, str]` (score, is_active, match_type).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_program.py
from app.scoring.program import program_fit

FOS_EXACT_MATCH = [
    {"cip_code": "11.0701", "credential_level": "bachelors", "graduates": 200,
     "median_earnings": 90000, "median_debt": 15000},
]


def test_inactive_when_no_major_specified():
    score, active, match_type = program_fit(None, [], [], {}, 100, 60000)
    assert active is False


def test_exact_match_scores_higher_than_related_only():
    exact_score, active, match_type = program_fit(
        "11", ["11.0701"], FOS_EXACT_MATCH, {"11": 0.2}, 100, 60000
    )
    assert active is True
    assert match_type == "exact"

    related_score, _, related_type = program_fit(
        "11", ["11.9999"], [], {"11": 0.2}, 100, 60000
    )
    assert related_type == "related"
    assert exact_score > related_score


def test_prominence_uses_national_median_anchor_not_pool_relative():
    # same inputs, called independently, must give the same score regardless
    # of any other schools "in the pool" (there is no pool parameter at all)
    score_a, _, _ = program_fit("11", ["11.0701"], FOS_EXACT_MATCH, {}, 100, 60000)
    score_b, _, _ = program_fit("11", ["11.0701"], FOS_EXACT_MATCH, {}, 100, 60000)
    assert score_a == score_b


def test_missing_program_level_earnings_falls_back_to_neutral():
    fos_no_earnings = [{"cip_code": "11.0701", "credential_level": "bachelors",
                         "graduates": 50, "median_earnings": None, "median_debt": None}]
    score, active, match_type = program_fit("11", ["11.0701"], fos_no_earnings, {}, 100, 60000)
    assert active is True
    assert 0 < score <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_program.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Write `program.py`**

```python
# backend/app/scoring/program.py
def _find_exact(field_of_study, cip_4digit_candidates):
    for rec in field_of_study:
        if rec["cip_code"] in cip_4digit_candidates and rec["credential_level"] == "bachelors":
            return rec
    return None


def program_fit(cip_2digit, cip_4digit_candidates, field_of_study, cip2_percentages,
                 national_median_grad_count, national_median_earnings):
    if not cip_2digit:
        return 0.0, False, "inactive"

    exact = _find_exact(field_of_study, cip_4digit_candidates)
    if exact:
        match_multiplier, match_type = 1.0, "exact"
        grads, earnings = exact.get("graduates"), exact.get("median_earnings")
    else:
        match_multiplier, match_type = 0.6, "related"
        grads, earnings = None, None

    if grads is not None and national_median_grad_count:
        prominence = min(1.0, grads / national_median_grad_count)
    else:
        prominence = min(1.0, cip2_percentages.get(cip_2digit, 0.0) / 0.15)

    if earnings is not None and national_median_earnings:
        outcomes = min(1.0, earnings / national_median_earnings)
    else:
        outcomes = 0.5

    score = match_multiplier * (0.5 * prominence + 0.5 * outcomes)
    return score, True, match_type
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_program.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/scoring/program.py backend/tests/test_program.py
git commit -m "feat: add program fit scoring using field-of-study data"
```

---

## Task 7: Campus size scoring

**Files:**
- Create: `backend/app/scoring/campus_size.py`
- Test: `backend/tests/test_campus_size.py`

**Interfaces:**
- Produces: `campus_size_fit(enrollment: int | None, stated: bool, preference: str | None, importance: str) -> tuple[float, bool]`, `SIZE_BANDS: dict[str, tuple[float, float]]`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_campus_size.py
from app.scoring.campus_size import campus_size_fit


def test_inactive_when_not_stated():
    score, active = campus_size_fit(8000, False, None, "not_mentioned")
    assert active is False


def test_any_school_inside_band_gets_max_score():
    low_end, active1 = campus_size_fit(4900, True, "small", "preferred")
    mid, active2 = campus_size_fit(2500, True, "small", "preferred")
    assert active1 and active2
    assert low_end == mid == 1.0  # both inside [0, 5000), not "closer to midpoint is better"


def test_outside_band_decays_toward_zero():
    just_outside, _ = campus_size_fit(5200, True, "small", "preferred")
    far_outside, _ = campus_size_fit(20000, True, "small", "preferred")
    assert 0 < just_outside < 1.0
    assert far_outside < just_outside
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_campus_size.py -v`
Expected: FAIL

- [ ] **Step 3: Write `campus_size.py`**

```python
# backend/app/scoring/campus_size.py
SIZE_BANDS = {"small": (0, 5000), "medium": (5000, 15000), "large": (15000, float("inf"))}


def campus_size_fit(enrollment, stated, preference, importance):
    if not stated or importance == "not_mentioned" or enrollment is None:
        return 0.0, False
    lo, hi = SIZE_BANDS[preference]
    if lo <= enrollment < hi:
        return 1.0, True
    band_width = (hi - lo) if hi != float("inf") else 5000
    overshoot = (lo - enrollment) if enrollment < lo else (enrollment - hi)
    return max(0.0, 1 - overshoot / band_width), True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_campus_size.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/scoring/campus_size.py backend/tests/test_campus_size.py
git commit -m "feat: add campus size scoring with absolute bands"
```

---

## Task 8: Weighting (active-dimension renormalization)

**Files:**
- Create: `backend/app/scoring/weighting.py`
- Test: `backend/tests/test_weighting.py`

**Interfaces:**
- Produces: `compute_weights(active: dict[str, bool], importances: dict[str, str]) -> dict[str, float]` where keys are `"program"`, `"geography"`, `"affordability"`, `"campus_size"` and values sum to 100 (or all 0 if nothing active).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_weighting.py
from app.scoring.weighting import compute_weights


def test_all_inactive_gives_all_zero_weights():
    weights = compute_weights(
        {"program": False, "geography": False, "affordability": False, "campus_size": False},
        {},
    )
    assert weights == {"program": 0.0, "geography": 0.0, "affordability": 0.0, "campus_size": 0.0}


def test_only_active_dimensions_get_nonzero_weight_and_sum_to_100():
    weights = compute_weights(
        {"program": True, "geography": True, "affordability": False, "campus_size": False},
        {"program": "default", "geography": "default"},
    )
    assert weights["affordability"] == 0.0
    assert weights["campus_size"] == 0.0
    assert weights["program"] == 50.0
    assert weights["geography"] == 50.0


def test_preferred_dimension_gets_boosted_over_default():
    weights = compute_weights(
        {"program": True, "geography": True, "affordability": False, "campus_size": False},
        {"program": "preferred", "geography": "default"},
    )
    assert weights["program"] > weights["geography"]
    assert abs(sum(weights.values()) - 100.0) < 1e-9


def test_uniform_importance_falls_back_to_equal_base_proportions():
    weights = compute_weights(
        {"program": True, "geography": True, "affordability": True, "campus_size": True},
        {},  # nothing specified -> all default to "default" -> uniform multiplier
    )
    assert weights["program"] == weights["geography"] == weights["affordability"] == weights["campus_size"] == 25.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_weighting.py -v`
Expected: FAIL

- [ ] **Step 3: Write `weighting.py`**

```python
# backend/app/scoring/weighting.py
BASE_WEIGHTS = {"program": 25.0, "geography": 25.0, "affordability": 25.0, "campus_size": 25.0}
IMPORTANCE_MULTIPLIER = {"not_mentioned": 1.0, "default": 1.0, "preferred": 1.4, "required": 1.4}


def compute_weights(active: dict, importances: dict) -> dict:
    raw = {}
    for dim, is_active in active.items():
        if not is_active:
            continue
        multiplier = IMPORTANCE_MULTIPLIER.get(importances.get(dim, "default"), 1.0)
        raw[dim] = BASE_WEIGHTS[dim] * multiplier

    result = {dim: 0.0 for dim in BASE_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return result
    for dim, value in raw.items():
        result[dim] = (value / total) * 100.0
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_weighting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/scoring/weighting.py backend/tests/test_weighting.py
git commit -m "feat: add active-dimension weight renormalization"
```

---

## Task 9: Reach/Target/Likely bucket assignment

**Files:**
- Create: `backend/app/scoring/bucket.py`
- Test: `backend/tests/test_bucket.py`

**Interfaces:**
- Produces: `assign_bucket(admission_rate: float | None, sat_p25: int | None, sat_p75: int | None, student_sat: int | None) -> tuple[str, str]` (bucket label, confidence).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_bucket.py
from app.scoring.bucket import assign_bucket


def test_very_selective_school_is_always_reach_even_with_high_sat():
    bucket, confidence = assign_bucket(admission_rate=0.04, sat_p25=1460, sat_p75=1580, student_sat=1560)
    assert bucket == "Reach"
    assert confidence == "high"


def test_moderately_selective_school_never_labeled_likely():
    # 18% would have been Likely under a naive "sat > p75" rule; the banded
    # guardrail must keep it out of Likely entirely
    bucket, _ = assign_bucket(admission_rate=0.30, sat_p25=1300, sat_p75=1450, student_sat=1500)
    assert bucket in ("Reach", "Target")
    assert bucket != "Likely"


def test_high_admit_rate_and_sat_well_above_range_is_likely():
    bucket, confidence = assign_bucket(admission_rate=0.75, sat_p25=1000, sat_p75=1150, student_sat=1300)
    assert bucket == "Likely"
    assert confidence == "high"


def test_test_optional_school_uses_admission_rate_only_with_medium_confidence():
    bucket, confidence = assign_bucket(admission_rate=0.10, sat_p25=None, sat_p75=None, student_sat=1200)
    assert bucket == "Reach"
    assert confidence == "medium"


def test_missing_all_data_defaults_to_target_with_low_confidence():
    bucket, confidence = assign_bucket(admission_rate=None, sat_p25=None, sat_p75=None, student_sat=1200)
    assert bucket == "Target"
    assert confidence == "low"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_bucket.py -v`
Expected: FAIL

- [ ] **Step 3: Write `bucket.py`**

```python
# backend/app/scoring/bucket.py
def assign_bucket(admission_rate, sat_p25, sat_p75, student_sat):
    has_sat = sat_p25 is not None and sat_p75 is not None and student_sat is not None
    has_rate = admission_rate is not None

    if has_sat and has_rate:
        confidence = "high"
        if admission_rate < 0.20:
            return "Reach", confidence
        if admission_rate < 0.40:
            return ("Reach" if student_sat < sat_p25 else "Target"), confidence
        if admission_rate < 0.60:
            return ("Target" if student_sat < sat_p75 else "Likely"), confidence
        return ("Target" if student_sat < sat_p25 else "Likely"), confidence

    if has_rate:
        confidence = "medium"
        if admission_rate < 0.20:
            return "Reach", confidence
        if admission_rate < 0.50:
            return "Target", confidence
        return "Likely", confidence

    return "Target", "low"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_bucket.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/scoring/bucket.py backend/tests/test_bucket.py
git commit -m "feat: add admission-rate-banded Reach/Target/Likely bucketing"
```

---

## Task 10: Dream school resolution

**Files:**
- Create: `backend/app/dream_schools.py`
- Test: `backend/tests/test_dream_schools.py`

**Interfaces:**
- Consumes: `find_school_by_name` from Task 3.
- Produces: `resolve_dream_school(conn, name: str, required_state: str | None, required_budget: float | None) -> dict` returning `{"status": "included" | "exception" | "excluded", "school": dict | None, "reason": str | None}`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_dream_schools.py
import tempfile
import os
from tests.fixtures.sample_schools import build_fixture_db
from app.db import get_connection
from app.dream_schools import resolve_dream_school


def _conn(tmp):
    path = os.path.join(tmp, "scorecard.sqlite")
    build_fixture_db(path)
    return get_connection(path)


def test_unmatched_name_is_excluded_with_warning():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Totally Fictional University", None, None)
        assert result["status"] == "excluded"
        assert "Totally Fictional University" in result["reason"]


def test_closed_school_is_excluded():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Closed Institute of Technology", None, None)
        assert result["status"] == "excluded"


def test_valid_school_violating_required_state_is_an_exception():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Massachusetts Institute of Technology", "PA", None)
        assert result["status"] == "exception"
        assert result["school"]["name"] == "Massachusetts Institute of Technology"
        assert "PA" in result["reason"]


def test_valid_school_satisfying_constraints_is_included():
    with tempfile.TemporaryDirectory() as tmp:
        conn = _conn(tmp)
        result = resolve_dream_school(conn, "Drexel University", "PA", None)
        assert result["status"] == "included"
        assert result["school"]["name"] == "Drexel University"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_dream_schools.py -v`
Expected: FAIL

- [ ] **Step 3: Write `dream_schools.py`**

```python
# backend/app/dream_schools.py
from app.db import find_school_by_name


def resolve_dream_school(conn, name, required_state, required_budget):
    school = find_school_by_name(conn, name)
    if school is None or not school["operating"] or not school["grants_bachelors"]:
        return {"status": "excluded", "school": None,
                "reason": f"Could not confirm current data for '{name}' — it may be "
                          f"closed or not currently degree-granting. Verify with the school directly."}

    if required_state and school["state"] != required_state:
        return {"status": "exception", "school": school,
                "reason": f"You named this as a dream school, but it's in {school['state']}, "
                          f"which conflicts with the requirement to stay in {required_state}."}
    if required_budget is not None and school["net_price_overall"] and school["net_price_overall"] > required_budget:
        return {"status": "exception", "school": school,
                "reason": f"You named this as a dream school, but its net price exceeds the stated budget."}

    return {"status": "included", "school": school, "reason": None}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_dream_schools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/dream_schools.py backend/tests/test_dream_schools.py
git commit -m "feat: add three-way dream school resolution"
```

---

## Task 11: Pipeline orchestration + golden fixture test

**Files:**
- Create: `backend/app/pipeline.py`
- Test: `backend/tests/test_pipeline_golden.py`

**Interfaces:**
- Consumes: all of Tasks 3-10.
- Produces: `run_pipeline(conn, profile: dict, national_medians: dict) -> dict` returning
  `{"colleges": [scored_college, ...], "dream_school_exceptions": [...], "relaxation_notes": [...]}`
  where each `scored_college` is
  `{"school": dict, "bucket": str, "confidence": str, "total_preference_score": float, "is_dream_school": bool, "program_match_type": str | None, "affordability_basis": str | None}`.
  `profile` is a plain dict matching the `StudentProfile` shape defined in Task 12 (deliberately
  a dict here, not the Pydantic model, so this module has no import dependency on `app.llm`).

- [ ] **Step 1: Write the failing golden test using the assignment's own two example prompts**

```python
# backend/tests/test_pipeline_golden.py
import tempfile
import os
from tests.fixtures.sample_schools import build_fixture_db
from app.db import get_connection
from app.pipeline import run_pipeline

NATIONAL_MEDIANS = {"grad_count": 100, "earnings": 60000}

JOHN_SMITH_PROFILE = {
    "academics": {"gpa": 3.5, "sat": 1230, "act": None, "ap_scores": []},
    "interests": {"raw_text": "loves programming", "cip_2digit": "11",
                  "cip_4digit_candidates": ["11.0701"], "importance": "preferred"},
    "location": {"home_state": "PA",
                 "geo": {"stated": True, "direction": "near", "importance": "preferred"},
                 "climate": {"stated": False, "preference": None, "importance": "not_mentioned"}},
    "financial": {"needs_aid": False, "stated_budget": None, "family_income": None,
                  "importance": "not_mentioned"},
    "campus_size": {"stated": False, "preference": None, "importance": "not_mentioned"},
    "dream_schools": [],
    "narrative_context": "Wants practical, hands-on programs; not too far from home.",
}


def test_john_smith_gets_a_nonempty_bucketed_list():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "scorecard.sqlite")
        build_fixture_db(path)
        conn = get_connection(path)

        result = run_pipeline(conn, JOHN_SMITH_PROFILE, NATIONAL_MEDIANS)

        assert len(result["colleges"]) > 0
        buckets_present = {c["bucket"] for c in result["colleges"]}
        assert buckets_present.issubset({"Reach", "Target", "Likely"})
        # Drexel (PA, in-state, CS program) should score at least as well on
        # geography as MIT (out of state) given a "near home" preference
        by_name = {c["school"]["name"]: c for c in result["colleges"]}
        assert "Drexel University" in by_name


def test_dream_school_always_appears_in_output():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "scorecard.sqlite")
        build_fixture_db(path)
        conn = get_connection(path)
        profile = dict(JOHN_SMITH_PROFILE)
        profile["dream_schools"] = [{"name": "Massachusetts Institute of Technology", "reason": "always dreamed of it"}]

        result = run_pipeline(conn, profile, NATIONAL_MEDIANS)

        names = {c["school"]["name"] for c in result["colleges"]}
        exception_names = {e["school"]["name"] for e in result["dream_school_exceptions"] if e.get("school")}
        assert "Massachusetts Institute of Technology" in names or "Massachusetts Institute of Technology" in exception_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_pipeline_golden.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.pipeline'`)

- [ ] **Step 3: Write `pipeline.py`**

```python
# backend/app/pipeline.py
from app.db import get_eligible_schools, get_field_of_study, get_cip2_percentages
from app.dream_schools import resolve_dream_school
from app.scoring.geography import geography_fit
from app.scoring.affordability import affordability_fit
from app.scoring.program import program_fit
from app.scoring.campus_size import campus_size_fit
from app.scoring.weighting import compute_weights
from app.scoring.bucket import assign_bucket

OCEAN_KEYWORDS = ("marine", "ocean", "oceanograph", "fisher")


def _is_ocean_related(interests: dict) -> bool:
    return any(k in interests.get("raw_text", "").lower() for k in OCEAN_KEYWORDS)


def _required_state(profile) -> str | None:
    geo = profile["location"]["geo"]
    if geo["importance"] == "required" and geo.get("direction") == "near":
        return profile["location"]["home_state"]
    return None


def _required_budget(profile) -> float | None:
    fin = profile["financial"]
    if fin["importance"] == "required" and fin.get("stated_budget") is not None:
        return fin["stated_budget"]
    return None


def _score_school(school, profile, national_medians):
    fos = get_field_of_study.__wrapped__ if False else None  # placeholder to keep import used
    return school


def score_one_school(conn, school, profile, national_medians):
    interests = profile["interests"]
    geo, climate = profile["location"]["geo"], profile["location"]["climate"]
    financial = profile["financial"]
    campus_size = profile["campus_size"]

    fos = get_field_of_study(conn, school["unit_id"])
    cip2 = get_cip2_percentages(conn, school["unit_id"])

    program_score, program_active, program_match_type = program_fit(
        interests.get("cip_2digit"), interests.get("cip_4digit_candidates", []),
        fos, cip2, national_medians["grad_count"], national_medians["earnings"],
    )
    geo_score, geo_active = geography_fit(
        profile["location"]["home_state"], school["state"],
        geo["stated"], geo["importance"], geo.get("direction"),
        climate["stated"], climate["importance"], _is_ocean_related(interests),
    )
    net_price_by_income = {
        "0-30000": school["net_price_income_0_30000"],
        "30001-48000": school["net_price_income_30001_48000"],
        "48001-75000": school["net_price_income_48001_75000"],
        "75001-110000": school["net_price_income_75001_110000"],
        "110001-plus": school["net_price_income_110001_plus"],
    }
    afford_score, afford_active, afford_basis = affordability_fit(
        school["net_price_overall"], net_price_by_income,
        financial.get("stated_budget"), financial.get("family_income"),
        financial["needs_aid"], financial["importance"],
    )
    size_score, size_active = campus_size_fit(
        school["enrollment"], campus_size["stated"], campus_size.get("preference"), campus_size["importance"],
    )

    weights = compute_weights(
        {"program": program_active, "geography": geo_active,
         "affordability": afford_active, "campus_size": size_active},
        {"program": interests["importance"], "geography": geo["importance"],
         "affordability": financial["importance"], "campus_size": campus_size["importance"]},
    )
    total = (weights["program"] * program_score + weights["geography"] * geo_score +
             weights["affordability"] * afford_score + weights["campus_size"] * size_score) / 100.0

    bucket, confidence = assign_bucket(
        school["admission_rate"], school["sat_p25"], school["sat_p75"], profile["academics"].get("sat"),
    )

    return {
        "school": school, "bucket": bucket, "confidence": confidence,
        "total_preference_score": total, "is_dream_school": False,
        "program_match_type": program_match_type if program_active else None,
        "affordability_basis": afford_basis if afford_active else None,
    }


TARGET_COUNTS = {"Reach": 3, "Target": 4, "Likely": 3}


def run_pipeline(conn, profile, national_medians):
    interests = profile["interests"]
    eligible = get_eligible_schools(
        conn, cip_2digit=interests.get("cip_2digit"),
        required_state=_required_state(profile), required_budget=_required_budget(profile),
    )
    scored = [score_one_school(conn, s, profile, national_medians) for s in eligible]

    dream_results = [
        resolve_dream_school(conn, d["name"], _required_state(profile), _required_budget(profile))
        for d in profile.get("dream_schools", [])
    ]
    exceptions = [r for r in dream_results if r["status"] in ("exception", "excluded")]
    for r in dream_results:
        if r["status"] == "included":
            already = next((s for s in scored if s["school"]["unit_id"] == r["school"]["unit_id"]), None)
            if already:
                already["is_dream_school"] = True
            else:
                dream_scored = score_one_school(conn, r["school"], profile, national_medians)
                dream_scored["is_dream_school"] = True
                scored.append(dream_scored)

    relaxation_notes = []
    final = []
    by_bucket = {"Reach": [], "Target": [], "Likely": []}
    for s in scored:
        by_bucket[s["bucket"]].append(s)
    for bucket, target_count in TARGET_COUNTS.items():
        pool = sorted(by_bucket[bucket], key=lambda s: s["total_preference_score"], reverse=True)
        chosen = pool[:target_count]
        chosen_ids = {c["school"]["unit_id"] for c in chosen}
        for s in pool:
            if s["is_dream_school"] and s["school"]["unit_id"] not in chosen_ids:
                chosen.append(s)
        if len(pool) < target_count:
            relaxation_notes.append(
                f"Only {len(pool)} eligible {bucket} schools were found; showing all of them."
            )
        final.extend(chosen)

    return {"colleges": final, "dream_school_exceptions": exceptions, "relaxation_notes": relaxation_notes}
```

(Delete the unused `_score_school` placeholder before committing — it was a scratch note, not code
to ship.)

- [ ] **Step 4: Remove the scratch placeholder and re-check**

Delete the `_score_school` function entirely from `pipeline.py` (it is dead code left over from
drafting and is not used anywhere).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_pipeline_golden.py -v`
Expected: PASS

- [ ] **Step 6: Run the full backend test suite to confirm no regressions**

Run: `cd backend && pytest -v`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/pipeline.py backend/tests/test_pipeline_golden.py
git commit -m "feat: orchestrate candidate retrieval, bucketing, scoring, and shortlisting"
```

---

## Task 12: StudentProfile schema + LLM Call #1 (profile extraction)

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/llm/__init__.py` (empty)
- Create: `backend/app/llm/client.py`
- Create: `backend/app/llm/profile_extraction.py`
- Test: `backend/tests/test_profile_extraction.py`

**Interfaces:**
- Produces: `app.schemas.StudentProfile` (Pydantic model matching the dict shape used in Task 11 — `.model_dump()` produces that exact dict shape). `app.llm.client.get_client() -> anthropic.Anthropic`. `app.llm.profile_extraction.extract_profile(client, description: str) -> StudentProfile`, raises `ProfileExtractionError` after one failed retry.

- [ ] **Step 1: Write `schemas.py`**

```python
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
```

- [ ] **Step 2: Write `client.py`**

```python
# backend/app/llm/client.py
import anthropic
from app.config import get_settings


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
```

- [ ] **Step 3: Write the failing test for `extract_profile` (Anthropic client mocked)**

```python
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && pytest tests/test_profile_extraction.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.llm.profile_extraction'`)

- [ ] **Step 5: Write `profile_extraction.py`**

```python
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_profile_extraction.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/llm/__init__.py backend/app/llm/client.py backend/app/llm/profile_extraction.py backend/tests/test_profile_extraction.py
git commit -m "feat: add StudentProfile schema and schema-validated LLM profile extraction"
```

---

## Task 13: LLM Call #2 (grounded explanation)

**Files:**
- Create: `backend/app/llm/explanation.py`
- Test: `backend/tests/test_explanation.py`

**Interfaces:**
- Consumes: the `scored_college` dict shape from Task 11, `StudentProfile` from Task 12.
- Produces: `generate_explanations(client, profile: StudentProfile, colleges: list[dict]) -> tuple[str, dict[int, str]]` (overall summary, `unit_id -> rationale` map). Falls back to a templated rationale per-school if the LLM output can't be matched back to the locked `unit_id`s it was given.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_explanation.py -v`
Expected: FAIL

- [ ] **Step 3: Write `explanation.py`**

```python
# backend/app/llm/explanation.py
import json

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


def generate_explanations(client, profile, colleges):
    response = client.messages.create(
        model="claude-sonnet-4-5", max_tokens=1024, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(profile, colleges)}],
    )
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
        summary = "Here is a college list built from your student's real academic profile and stated preferences."
        rationales = {c["school"]["unit_id"]: _template_rationale(c) for c in colleges}
        return summary, rationales
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_explanation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/explanation.py backend/tests/test_explanation.py
git commit -m "feat: add grounded LLM explanation step with template fallback"
```

---

## Task 14: `/api/generate-list` endpoint

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `extract_profile`, `run_pipeline`, `generate_explanations`, `GenerateListRequest`/`GenerateListResponse` from prior tasks.
- Produces: `POST /api/generate-list`.

- [ ] **Step 1: Write the failing test (LLM calls mocked, uses fixture DB)**

```python
# backend/tests/test_api.py (append to existing file)
import tempfile
import os
from unittest.mock import patch, MagicMock
from tests.fixtures.sample_schools import build_fixture_db


def _mock_extraction_response():
    block = MagicMock()
    block.type = "tool_use"
    block.input = {
        "academics": {"gpa": 3.5, "sat": 1230, "act": None, "ap_scores": []},
        "interests": {"raw_text": "loves programming", "cip_2digit": "11",
                      "cip_4digit_candidates": [], "importance": "preferred"},
        "location": {"home_state": "PA",
                     "geo": {"stated": True, "direction": "near", "importance": "preferred"},
                     "climate": {"stated": False, "preference": None, "importance": "not_mentioned"}},
        "financial": {"needs_aid": False, "stated_budget": None, "family_income": None,
                      "importance": "not_mentioned"},
        "campus_size": {"stated": False, "preference": None, "importance": "not_mentioned"},
        "dream_schools": [], "narrative_context": "practical, hands-on",
    }
    response = MagicMock()
    response.content = [block]
    return response


def _mock_explanation_response():
    import json
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps({"summary": "A solid list.", "rationales": {}})
    response = MagicMock()
    response.content = [block]
    return response


def test_generate_list_returns_bucketed_colleges(tmp_path, monkeypatch):
    db_path = os.path.join(tmp_path, "scorecard.sqlite")
    build_fixture_db(db_path)
    monkeypatch.setenv("SCORECARD_DB_PATH", db_path)
    from app.config import get_settings
    get_settings.cache_clear()

    with patch("app.llm.client.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.side_effect = [_mock_extraction_response(), _mock_explanation_response()]

        response = client.post("/api/generate-list", json={"description": "loves programming, 1230 SAT, PA, wants to stay close to home"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["colleges"]) > 0
    assert body["scoring_version"]
    assert body["scorecard_data_year"] == "test-fixture"
    get_settings.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api.py::test_generate_list_returns_bucketed_colleges -v`
Expected: FAIL (404, route doesn't exist)

- [ ] **Step 3: Add the route to `main.py`**

```python
# backend/app/main.py (replace file contents)
import datetime
from fastapi import FastAPI, HTTPException
from app.config import get_settings
from app.db import get_connection
from app.llm.client import get_client
from app.llm.profile_extraction import extract_profile, ProfileExtractionError
from app.llm.explanation import generate_explanations
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
```

Also add the `client = TestClient(app)` import line at the top of `test_api.py` if not already
present from Task 1 (it is — reuse it).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite**

Run: `cd backend && pytest -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat: add /api/generate-list endpoint wiring extraction, pipeline, and explanation"
```

---

## Task 15: PDF star-chart drawing + `/api/generate-pdf`

**Files:**
- Create: `backend/app/pdf/__init__.py` (empty)
- Create: `backend/app/pdf/chart.py`
- Create: `backend/app/pdf/generate.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_pdf_chart.py`

**Interfaces:**
- Produces: `app.pdf.chart.compute_star_positions(colleges: list[dict]) -> list[dict]` (pure geometry: returns `{"unit_id", "name", "bucket", "x", "y"}` per school, center at `(0, 0)`, ring radius by bucket). `app.pdf.generate.build_pdf(response: GenerateListResponse) -> bytes`. Route: `POST /api/generate-pdf`.

- [ ] **Step 1: Write the failing geometry test**

```python
# backend/tests/test_pdf_chart.py
import math
from app.pdf.chart import compute_star_positions

COLLEGES = [
    {"school": {"unit_id": 1, "name": "A"}, "bucket": "Reach"},
    {"school": {"unit_id": 2, "name": "B"}, "bucket": "Target"},
    {"school": {"unit_id": 3, "name": "C"}, "bucket": "Likely"},
]


def test_reach_schools_are_farther_from_center_than_likely():
    positions = compute_star_positions(COLLEGES)
    by_bucket = {p["bucket"]: p for p in positions}
    reach_dist = math.hypot(by_bucket["Reach"]["x"], by_bucket["Reach"]["y"])
    target_dist = math.hypot(by_bucket["Target"]["x"], by_bucket["Target"]["y"])
    likely_dist = math.hypot(by_bucket["Likely"]["x"], by_bucket["Likely"]["y"])
    assert reach_dist > target_dist > likely_dist


def test_every_college_gets_a_position():
    positions = compute_star_positions(COLLEGES)
    assert {p["unit_id"] for p in positions} == {1, 2, 3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_pdf_chart.py -v`
Expected: FAIL

- [ ] **Step 3: Write `chart.py`**

```python
# backend/app/pdf/chart.py
import math

RING_RADIUS = {"Reach": 200, "Target": 130, "Likely": 65}


def compute_star_positions(colleges: list[dict]) -> list[dict]:
    by_bucket: dict[str, list[dict]] = {"Reach": [], "Target": [], "Likely": []}
    for c in colleges:
        by_bucket[c["bucket"]].append(c)

    positions = []
    for bucket, items in by_bucket.items():
        radius = RING_RADIUS[bucket]
        n = len(items)
        for i, c in enumerate(items):
            angle = (2 * math.pi * i / n) if n else 0
            positions.append({
                "unit_id": c["school"]["unit_id"], "name": c["school"]["name"], "bucket": bucket,
                "x": radius * math.cos(angle), "y": radius * math.sin(angle),
            })
    return positions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_pdf_chart.py -v`
Expected: PASS

- [ ] **Step 5: Write `generate.py`**

```python
# backend/app/pdf/generate.py
from io import BytesIO
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from app.pdf.chart import compute_star_positions

PARCHMENT = HexColor("#EDE3C8")
INK_NAVY = HexColor("#1B2A4A")
GOLD_LEAF = HexColor("#B8862E")
BUCKET_COLORS = {"Reach": HexColor("#9B3B26"), "Target": HexColor("#5C6E4A"), "Likely": HexColor("#2E5C55")}


def _draw_chart(c, colleges, center_x, center_y):
    c.setFillColor(GOLD_LEAF)
    c.circle(center_x, center_y, 6, fill=1, stroke=0)
    for pos in compute_star_positions(colleges):
        x, y = center_x + pos["x"], center_y + pos["y"]
        c.setStrokeColor(INK_NAVY)
        c.setLineWidth(0.5)
        c.line(center_x, center_y, x, y)
        c.setFillColor(BUCKET_COLORS[pos["bucket"]])
        c.circle(x, y, 4, fill=1, stroke=0)


def build_pdf(response) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    c.setFillColor(PARCHMENT)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    c.setFillColor(INK_NAVY)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 60, "College Compass")

    college_dicts = [
        {"school": {"unit_id": i, "name": entry.name}, "bucket": entry.bucket}
        for i, entry in enumerate(response.colleges)
    ]
    _draw_chart(c, college_dicts, width / 2, height - 220)

    y = height - 420
    c.setFont("Helvetica", 11)
    for entry in response.colleges:
        c.setFillColor(BUCKET_COLORS[entry.bucket])
        c.circle(60, y + 3, 3, fill=1, stroke=0)
        c.setFillColor(INK_NAVY)
        c.drawString(75, y, f"{entry.name} — {entry.bucket} ({entry.state})")
        y -= 16
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(75, y, entry.rationale[:110])
        c.setFont("Helvetica", 11)
        y -= 20
        if y < 60:
            c.showPage()
            c.setFillColor(PARCHMENT)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            y = height - 60

    c.save()
    return buffer.getvalue()
```

- [ ] **Step 6: Add the route to `main.py`**

```python
# backend/app/main.py (add import + route)
from fastapi.responses import Response
from app.pdf.generate import build_pdf

# ... after generate_list ...

@app.post("/api/generate-pdf")
def generate_pdf(response_body: GenerateListResponse):
    pdf_bytes = build_pdf(response_body)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=college-compass-list.pdf"},
    )
```

- [ ] **Step 7: Write and run a smoke test for the PDF route**

```python
# backend/tests/test_api.py (append)
def test_generate_pdf_returns_pdf_bytes():
    payload = {
        "student_summary": "Test summary", "colleges": [
            {"name": "Drexel University", "state": "PA", "bucket": "Target", "confidence": "high",
             "admission_rate": 0.76, "sat_p25": 1160, "sat_p75": 1380, "program_match_type": "exact",
             "net_price": 32000, "affordability_basis": None, "is_dream_school": False,
             "rationale": "Strong co-op program fit."}
        ],
        "dream_school_exceptions": [], "relaxation_notes": [],
        "generated_at": "2026-01-01T00:00:00", "scoring_version": "v1.0", "scorecard_data_year": "test",
    }
    response = client.post("/api/generate-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"
```

Run: `cd backend && pytest tests/test_api.py::test_generate_pdf_returns_pdf_bytes -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/pdf/ backend/app/main.py backend/tests/test_pdf_chart.py backend/tests/test_api.py
git commit -m "feat: add ReportLab star-chart PDF generation and /api/generate-pdf"
```

---

## Task 16: Vue scaffold + design tokens

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/style/tokens.css`

**Interfaces:**
- Produces: a runnable Vite dev server with the design-token CSS variables available globally.

- [ ] **Step 1: Scaffold the project**

```bash
cd frontend
npm create vite@latest . -- --template vue-ts
npm install
```

- [ ] **Step 2: Write `tokens.css`**

```css
/* frontend/src/style/tokens.css */
@import url('https://fonts.googleapis.com/css2?family=Cormorant:ital,wght@0,500;0,700;1,500&family=Spectral:wght@400;600&family=Space+Mono:wght@400;700&display=swap');

:root {
  --parchment: #EDE3C8;
  --ink-navy: #1B2A4A;
  --gold-leaf: #B8862E;
  --reach-ember: #9B3B26;
  --target-sage: #5C6E4A;
  --likely-teal: #2E5C55;
  --font-display: 'Cormorant', serif;
  --font-body: 'Spectral', serif;
  --font-data: 'Space Mono', monospace;
}

body {
  background: var(--parchment);
  color: var(--ink-navy);
  font-family: var(--font-body);
  margin: 0;
}
```

- [ ] **Step 3: Write `main.ts`, `App.vue`, `index.html`**

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>College Compass</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

```typescript
// frontend/src/main.ts
import { createApp } from 'vue'
import App from './App.vue'
import './style/tokens.css'

createApp(App).mount('#app')
```

```vue
<!-- frontend/src/App.vue (placeholder shell — filled in fully in Task 18) -->
<script setup lang="ts"></script>
<template>
  <main>
    <p>College Compass</p>
  </main>
</template>
```

- [ ] **Step 4: Run the dev server to confirm it boots**

Run: `cd frontend && npm run dev`
Expected: Vite prints a local URL; opening it shows the parchment background and "College Compass" text in the Spectral font (confirm via browser dev tools that the Google Font loaded, not a fallback serif).

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/index.html frontend/src/main.ts frontend/src/App.vue frontend/src/style/tokens.css frontend/.gitignore
git commit -m "feat: scaffold Vue frontend with celestial-atlas design tokens"
```

---

## Task 17: Star chart geometry (pure TS) + StarChart.vue

**Files:**
- Create: `frontend/src/chart/geometry.ts`
- Create: `frontend/src/chart/geometry.test.ts`
- Create: `frontend/src/components/StarChart.vue`
- Create: `frontend/vitest.config.ts`

**Interfaces:**
- Produces: `computeStarPositions(colleges: CollegeForChart[]): StarPosition[]` (mirrors the backend's `compute_star_positions` from Task 15 — same ring-radius-by-bucket logic, kept independent since the frontend renders live while the PDF is generated server-side from the same underlying data). `StarChart.vue` — props `{ colleges: CollegeForChart[], studentName: string }`, emits `select(unitId: number)`.

- [ ] **Step 1: Install Vitest**

```bash
cd frontend
npm install -D vitest
```

```typescript
// frontend/vitest.config.ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: { environment: 'jsdom' },
})
```

```bash
npm install -D jsdom
```

Add to `frontend/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 2: Write the failing geometry test**

```typescript
// frontend/src/chart/geometry.test.ts
import { describe, it, expect } from 'vitest'
import { computeStarPositions } from './geometry'

describe('computeStarPositions', () => {
  it('places Reach schools farther from center than Likely', () => {
    const positions = computeStarPositions([
      { unitId: 1, name: 'A', bucket: 'Reach' },
      { unitId: 2, name: 'B', bucket: 'Target' },
      { unitId: 3, name: 'C', bucket: 'Likely' },
    ])
    const dist = (p: { x: number; y: number }) => Math.hypot(p.x, p.y)
    const byBucket = Object.fromEntries(positions.map((p) => [p.bucket, p]))
    expect(dist(byBucket.Reach)).toBeGreaterThan(dist(byBucket.Target))
    expect(dist(byBucket.Target)).toBeGreaterThan(dist(byBucket.Likely))
  })

  it('gives every college a position', () => {
    const positions = computeStarPositions([
      { unitId: 1, name: 'A', bucket: 'Reach' },
      { unitId: 2, name: 'B', bucket: 'Target' },
    ])
    expect(positions.map((p) => p.unitId).sort()).toEqual([1, 2])
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm run test`
Expected: FAIL (`Cannot find module './geometry'`)

- [ ] **Step 4: Write `geometry.ts`**

```typescript
// frontend/src/chart/geometry.ts
export type Bucket = 'Reach' | 'Target' | 'Likely'

export interface CollegeForChart {
  unitId: number
  name: string
  bucket: Bucket
}

export interface StarPosition {
  unitId: number
  name: string
  bucket: Bucket
  x: number
  y: number
}

const RING_RADIUS: Record<Bucket, number> = { Reach: 200, Target: 130, Likely: 65 }

export function computeStarPositions(colleges: CollegeForChart[]): StarPosition[] {
  const byBucket: Record<Bucket, CollegeForChart[]> = { Reach: [], Target: [], Likely: [] }
  for (const c of colleges) byBucket[c.bucket].push(c)

  const positions: StarPosition[] = []
  ;(Object.keys(byBucket) as Bucket[]).forEach((bucket) => {
    const items = byBucket[bucket]
    const radius = RING_RADIUS[bucket]
    items.forEach((c, i) => {
      const angle = items.length ? (2 * Math.PI * i) / items.length : 0
      positions.push({
        unitId: c.unitId,
        name: c.name,
        bucket,
        x: radius * Math.cos(angle),
        y: radius * Math.sin(angle),
      })
    })
  })
  return positions
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm run test`
Expected: PASS

- [ ] **Step 6: Write `StarChart.vue`**

```vue
<!-- frontend/src/components/StarChart.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import { computeStarPositions, type CollegeForChart } from '../chart/geometry'

const props = defineProps<{
  colleges: CollegeForChart[]
  studentName: string
}>()

const emit = defineEmits<{ select: [unitId: number] }>()

const positions = computed(() => computeStarPositions(props.colleges))
const bucketColor: Record<string, string> = {
  Reach: 'var(--reach-ember)',
  Target: 'var(--target-sage)',
  Likely: 'var(--likely-teal)',
}
const center = 220
</script>

<template>
  <svg
    :viewBox="`0 0 ${center * 2} ${center * 2}`"
    class="star-chart"
    role="img"
    :aria-label="`Star chart for ${studentName}`"
  >
    <circle
      v-for="r in [65, 130, 200]"
      :key="r"
      :cx="center"
      :cy="center"
      :r="r"
      fill="none"
      stroke="var(--ink-navy)"
      stroke-width="0.5"
      opacity="0.4"
    />
    <line
      v-for="p in positions"
      :key="'line-' + p.unitId"
      :x1="center"
      :y1="center"
      :x2="center + p.x"
      :y2="center + p.y"
      stroke="var(--ink-navy)"
      stroke-width="0.5"
      opacity="0.5"
    />
    <circle :cx="center" :cy="center" r="7" fill="var(--gold-leaf)" class="student-star" />
    <text :x="center" :y="center - 12" text-anchor="middle" class="student-label">{{ studentName }}</text>
    <g v-for="p in positions" :key="p.unitId" class="star-point" @click="emit('select', p.unitId)">
      <circle :cx="center + p.x" :cy="center + p.y" r="5" :fill="bucketColor[p.bucket]" />
      <text :x="center + p.x" :y="center + p.y - 8" text-anchor="middle" class="school-label">
        {{ p.name }}
      </text>
    </g>
  </svg>
</template>

<style scoped>
.star-chart {
  width: 100%;
  max-width: 480px;
  display: block;
  margin: 0 auto;
}
.star-point {
  cursor: pointer;
}
.student-star {
  animation: twinkle 3s ease-in-out infinite;
}
.student-label {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 14px;
  fill: var(--ink-navy);
}
.school-label {
  font-family: var(--font-data);
  font-size: 9px;
  fill: var(--ink-navy);
}
@keyframes twinkle {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
@media (prefers-reduced-motion: reduce) {
  .student-star {
    animation: none;
  }
}
</style>
```

- [ ] **Step 7: Manual verification**

Temporarily render `<StarChart :colleges="[{unitId:1,name:'Test U',bucket:'Target'}]" studentName="Ada" />`
in `App.vue`, run `npm run dev`, confirm three concentric rings render, one gold student star at
center, one colored school star on the middle ring with a label, and clicking it doesn't error
(check the browser console). Revert `App.vue` to its Task 16 placeholder afterward — the real
wiring happens in Task 18.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/chart/ frontend/src/components/StarChart.vue frontend/vitest.config.ts frontend/package.json frontend/package-lock.json
git commit -m "feat: add star chart geometry and SVG celestial chart component"
```

---

## Task 18: Input/Results views, API wiring, PDF download

**Files:**
- Create: `frontend/src/api.ts`
- Create: `frontend/src/views/InputView.vue`
- Create: `frontend/src/components/SchoolCard.vue`
- Create: `frontend/src/views/ResultsView.vue`
- Modify: `frontend/src/App.vue`

**Interfaces:**
- Consumes: `GenerateListResponse` shape from Task 14 (`app.schemas.GenerateListResponse`), `StarChart.vue` from Task 17.
- Produces: a working input -> loading -> results -> PDF-download flow.

This task is UI wiring against an already-tested backend contract (Task 14) and an
already-tested chart primitive (Task 17); per the spec's lightweight testing scope, it is
verified by manual walkthrough against a running backend rather than component unit tests.

- [ ] **Step 1: Write `api.ts`**

```typescript
// frontend/src/api.ts
export interface CollegeEntry {
  name: string
  state: string
  bucket: 'Reach' | 'Target' | 'Likely'
  confidence: string
  admission_rate: number | null
  sat_p25: number | null
  sat_p75: number | null
  program_match_type: string | null
  net_price: number | null
  affordability_basis: string | null
  is_dream_school: boolean
  rationale: string
}

export interface GenerateListResponse {
  student_summary: string
  colleges: CollegeEntry[]
  dream_school_exceptions: { name: string; reason: string }[]
  relaxation_notes: string[]
  generated_at: string
  scoring_version: string
  scorecard_data_year: string
}

export async function generateList(description: string): Promise<GenerateListResponse> {
  const res = await fetch('/api/generate-list', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description }),
  })
  if (!res.ok) throw new Error(`Failed to generate list (${res.status})`)
  return res.json()
}

export async function downloadPdf(result: GenerateListResponse): Promise<void> {
  const res = await fetch('/api/generate-pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(result),
  })
  if (!res.ok) throw new Error(`Failed to generate PDF (${res.status})`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'college-compass-list.pdf'
  a.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 2: Write `InputView.vue`**

```vue
<!-- frontend/src/views/InputView.vue -->
<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ submit: [description: string] }>()
const description = ref('')

function handleSubmit() {
  if (description.value.trim().length < 10) return
  emit('submit', description.value)
}
</script>

<template>
  <div class="input-view">
    <h1 class="title">College Compass</h1>
    <p class="subtitle">Chart the stars for your student.</p>
    <textarea
      v-model="description"
      rows="8"
      placeholder="Describe the student in your own words — interests, scores, what they're looking for..."
    />
    <button class="chart-button" :disabled="description.trim().length < 10" @click="handleSubmit">
      Chart the Sky
    </button>
  </div>
</template>

<style scoped>
.input-view {
  max-width: 640px;
  margin: 4rem auto;
  padding: 2rem;
  text-align: center;
}
.title {
  font-family: var(--font-display);
  font-size: 3rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}
.subtitle {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 1.1rem;
  margin-bottom: 2rem;
}
textarea {
  width: 100%;
  font-family: var(--font-body);
  font-size: 1rem;
  padding: 1rem;
  border: 1px solid var(--ink-navy);
  background: rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  resize: vertical;
  box-sizing: border-box;
}
.chart-button {
  margin-top: 1.5rem;
  padding: 0.75rem 2rem;
  border-radius: 999px;
  border: 2px solid var(--gold-leaf);
  background: var(--gold-leaf);
  color: var(--parchment);
  font-family: var(--font-display);
  font-size: 1.1rem;
  cursor: pointer;
}
.chart-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
```

- [ ] **Step 3: Write `SchoolCard.vue`**

```vue
<!-- frontend/src/components/SchoolCard.vue -->
<script setup lang="ts">
import type { CollegeEntry } from '../api'
defineProps<{ college: CollegeEntry }>()
</script>

<template>
  <div class="school-card">
    <div class="header">
      <span class="name">{{ college.name }}</span>
      <span class="badge" :class="college.bucket.toLowerCase()">{{ college.bucket }}</span>
    </div>
    <p class="stats">
      {{ college.state }}
      <span v-if="college.admission_rate !== null">
        · {{ Math.round(college.admission_rate * 100) }}% admit rate
      </span>
      <span v-if="college.net_price !== null">
        · ${{ Math.round(college.net_price).toLocaleString() }}/yr net price
      </span>
    </p>
    <p class="rationale">{{ college.rationale }}</p>
  </div>
</template>

<style scoped>
.school-card {
  border: 1px solid var(--ink-navy);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  background: rgba(255, 255, 255, 0.25);
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.name {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 700;
}
.badge {
  font-family: var(--font-data);
  font-size: 0.7rem;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  color: white;
}
.badge.reach { background: var(--reach-ember); }
.badge.target { background: var(--target-sage); }
.badge.likely { background: var(--likely-teal); }
.stats {
  font-family: var(--font-data);
  font-size: 0.85rem;
  margin: 0.4rem 0;
}
.rationale {
  font-family: var(--font-body);
  font-size: 0.95rem;
}
</style>
```

- [ ] **Step 4: Write `ResultsView.vue`**

```vue
<!-- frontend/src/views/ResultsView.vue -->
<script setup lang="ts">
import StarChart from '../components/StarChart.vue'
import SchoolCard from '../components/SchoolCard.vue'
import { downloadPdf, type GenerateListResponse } from '../api'

const props = defineProps<{ result: GenerateListResponse; studentName: string }>()

const chartColleges = props.result.colleges.map((c, i) => ({
  unitId: i,
  name: c.name,
  bucket: c.bucket,
}))

function handleDownload() {
  downloadPdf(props.result)
}
</script>

<template>
  <div class="results-view">
    <StarChart :colleges="chartColleges" :student-name="studentName" />
    <p class="summary">{{ result.student_summary }}</p>
    <div class="cards">
      <SchoolCard v-for="college in result.colleges" :key="college.name" :college="college" />
    </div>
    <p v-for="note in result.relaxation_notes" :key="note" class="note">{{ note }}</p>
    <button class="seal-button" @click="handleDownload">Download PDF</button>
  </div>
</template>

<style scoped>
.results-view {
  max-width: 720px;
  margin: 2rem auto;
  padding: 1rem;
}
.summary {
  font-family: var(--font-body);
  font-style: italic;
  text-align: center;
  margin: 1rem 0 2rem;
}
.note {
  font-family: var(--font-data);
  font-size: 0.8rem;
  color: var(--reach-ember);
}
.seal-button {
  display: block;
  margin: 2rem auto 0;
  border-radius: 50%;
  width: 90px;
  height: 90px;
  border: 2px solid var(--gold-leaf);
  background: var(--gold-leaf);
  color: var(--parchment);
  font-family: var(--font-display);
  cursor: pointer;
}
</style>
```

- [ ] **Step 5: Wire it all together in `App.vue`**

```vue
<!-- frontend/src/App.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import InputView from './views/InputView.vue'
import ResultsView from './views/ResultsView.vue'
import { generateList, type GenerateListResponse } from './api'

const result = ref<GenerateListResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function handleSubmit(description: string) {
  loading.value = true
  error.value = null
  try {
    result.value = await generateList(description)
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Something went wrong. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main>
    <InputView v-if="!result && !loading" @submit="handleSubmit" />
    <p v-if="loading" class="status">Charting the sky...</p>
    <p v-if="error" class="status error">{{ error }}</p>
    <ResultsView v-if="result" :result="result" student-name="Your Student" />
  </main>
</template>

<style scoped>
.status {
  text-align: center;
  font-family: var(--font-display);
  font-style: italic;
  margin-top: 4rem;
}
.error {
  color: var(--reach-ember);
}
</style>
```

- [ ] **Step 6: Manual end-to-end verification**

Run the backend (`cd backend && uvicorn app.main:app --reload`, with `ANTHROPIC_API_KEY` and
`SCORECARD_DB_PATH` set to a real `scorecard.sqlite` built in Task 2's Step 6) and the frontend
dev server (`cd frontend && npm run dev`, with Vite's dev proxy forwarding `/api` to the backend
— add `server: { proxy: { '/api': 'http://localhost:8000' } }` to `vite.config.ts` if not already
present). Paste in the assignment's own two example prompts (the PA/CS student, the marine-biology
student) and confirm: the star chart renders with schools on the correct rings, the school cards
show real stats and a rationale, and "Download PDF" produces a readable file.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api.ts frontend/src/views/ frontend/src/components/SchoolCard.vue frontend/src/App.vue frontend/vite.config.ts
git commit -m "feat: wire input, results, and PDF download flow to the backend API"
```

---

## Task 19: Single-service deployment + README

**Files:**
- Modify: `backend/app/main.py`
- Create: `Dockerfile`
- Create: `README.md`
- Create: `.dockerignore`

**Interfaces:**
- Produces: one Docker image that builds the Vue frontend, builds `scorecard.sqlite`, and serves both the static frontend and the API from a single `uvicorn` process — deployable to Render's free web-service tier as a Docker service.

- [ ] **Step 1: Mount the built frontend as static files in `main.py`**

```python
# backend/app/main.py (add near the bottom, after all @app.route definitions)
import os
from fastapi.staticfiles import StaticFiles

_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")
```

This must be the **last** thing added to `main.py` — FastAPI matches routes in registration
order, so every `/api/*` route defined above it still takes precedence over the catch-all
static mount.

- [ ] **Step 2: Write the `Dockerfile`**

```dockerfile
# Dockerfile
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /frontend/dist ./static

ARG COLLEGE_SCORECARD_API_KEY
ENV COLLEGE_SCORECARD_API_KEY=${COLLEGE_SCORECARD_API_KEY}
RUN python -m scripts.refresh_data

ENV SCORECARD_DB_PATH=/app/scorecard.sqlite
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Write `.dockerignore`**

```
frontend/node_modules
frontend/dist
backend/tests
backend/**/__pycache__
.git
```

- [ ] **Step 4: Write `README.md`**

```markdown
# College Compass

## Setup

1. **Anthropic API key** (for the two Claude calls): sign up at
   https://console.anthropic.com, create an API key under "API Keys". A card is required to
   activate the account, but usage here is two short calls per request — trial credit covers
   a demo many times over.
2. **College Scorecard API key** (build-time only, to fetch real school data — no card
   required): sign up at https://collegescorecard.ed.gov/data/api-documentation/, a free key
   is emailed immediately.
3. Set environment variables:
   - `ANTHROPIC_API_KEY` — required at runtime.
   - `COLLEGE_SCORECARD_API_KEY` — required only when building the Docker image / running
     `refresh_data.py` (not needed at runtime — the app reads the local `scorecard.sqlite`
     built during that step).

## Run locally

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
COLLEGE_SCORECARD_API_KEY=<key> python -m scripts.refresh_data
ANTHROPIC_API_KEY=<key> uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

## Deploy (Render, free tier)

1. Push this repo to GitHub.
2. In Render, create a new Web Service, "Docker" runtime, point it at the repo.
3. Set the build-time env var `COLLEGE_SCORECARD_API_KEY` (Render supports build args for
   Docker builds) and the runtime env var `ANTHROPIC_API_KEY`.
4. Deploy. Render builds the Dockerfile (which fetches Scorecard data and bakes
   `scorecard.sqlite` into the image) and serves both the frontend and API from one URL.

To refresh the underlying Scorecard data later (e.g. next admissions cycle), trigger a new
deploy — the build step re-runs `refresh_data.py` against the then-current API.
```

- [ ] **Step 5: Manual verification of the Docker build**

Run: `docker build --build-arg COLLEGE_SCORECARD_API_KEY=<your key> -t college-compass .`
Expected: build completes, ending with the `scripts.refresh_data` print statement showing a
non-trivial institution count.

Run: `docker run -p 8000:8000 -e ANTHROPIC_API_KEY=<your key> college-compass`
Expected: visiting `http://localhost:8000` in a browser shows the College Compass input page
(served as static files), and submitting a description returns a real result.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py Dockerfile .dockerignore README.md
git commit -m "feat: add single-service Docker deployment and setup instructions"
```

---

## Self-Review

**Spec coverage:**
- Core thesis (LLM understands + explains, code decides) — Tasks 9-13.
- Build-time `scorecard.sqlite` from live API, local-only runtime reads — Tasks 2-3, 19.
- StudentProfile schema with closed `importance` enum — Task 12.
- Candidate universe / hard eligibility (operating, bachelor's, CIP availability, required-as-hard-filter) — Task 3.
- Dream school 3-way resolution — Task 10.
- Reach/Target/Likely banded guardrail + confidence — Task 9.
- Absolute-anchor scoring for geography/affordability/program/campus-size (not pool-relative) — Tasks 4-7.
- Active-dimension weight renormalization (inactive = 0, not a free perfect score) — Task 8.
- LLM Call #2 grounded-explanation-only with locked-fact validation and template fallback — Task 13.
- API contract (`/api/generate-list`, `/api/generate-pdf`) — Tasks 14-15.
- Celestial-atlas frontend (tokens, star chart, PDF continuity) — Tasks 16-18; PDF vector chart — Task 15.
- Golden E2E cases from the assignment's own two prompts — Task 11 (pipeline-level) and Task 18 Step 6 (full-stack manual pass).
- Deployment + API key setup — Task 19.
- Testing plan (schema, invariants, scoring unit tests, golden cases, failure handling) — spread across Tasks 4-15 as each module is built, per TDD, rather than bolted on afterward.

**Placeholder scan:** Task 11 originally included a scratch `_score_school` stub while
drafting the pipeline function — Step 4 of that task explicitly instructs deleting it before
committing, so no dead code ships. No other TBD/"add appropriate handling"-style gaps found.

**Type consistency:** `School` dict keys (`unit_id`, `net_price_overall`,
`net_price_income_0_30000`, etc. from Task 2/3) are used identically in Task 11's
`score_one_school` and Task 14's response assembly. `StudentProfile.model_dump()` (Task 12)
produces exactly the nested dict shape (`location.geo.stated`, `financial.importance`, etc.)
that `run_pipeline` (Task 11) and its fixture profiles expect — both were written against the
same schema definition. `scored_college` keys (`bucket`, `confidence`, `is_dream_school`,
`program_match_type`, `affordability_basis`) are produced once in Task 11 and consumed
identically in Tasks 13-15 without renaming.

---

Plan complete and saved to `docs/superpowers/plans/2026-09-04-college-list-builder.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
