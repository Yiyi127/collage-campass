import sqlite3
import datetime
import time
import httpx
import os

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
CREATE INDEX idx_field_of_study_unit_id ON field_of_study(unit_id);
CREATE INDEX idx_cip2_percentages_unit_id ON cip2_percentages(unit_id);
"""

CREDENTIAL_LEVEL_NAMES = {1: "certificate", 2: "associate", 3: "bachelors", 5: "masters", 6: "doctoral"}


def build_database(institution_records, field_of_study_records, db_path, scorecard_data_year):
    if os.path.exists(db_path):
        os.remove(db_path)
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
                _first_not_none(rec.get("latest.cost.net_price.public.by_income_level.0-30000"),
                                rec.get("latest.cost.net_price.private.by_income_level.0-30000")),
                _first_not_none(rec.get("latest.cost.net_price.public.by_income_level.30001-48000"),
                                rec.get("latest.cost.net_price.private.by_income_level.30001-48000")),
                _first_not_none(rec.get("latest.cost.net_price.public.by_income_level.48001-75000"),
                                rec.get("latest.cost.net_price.private.by_income_level.48001-75000")),
                _first_not_none(rec.get("latest.cost.net_price.public.by_income_level.75001-110000"),
                                rec.get("latest.cost.net_price.private.by_income_level.75001-110000")),
                _first_not_none(rec.get("latest.cost.net_price.public.by_income_level.110001-plus"),
                                rec.get("latest.cost.net_price.private.by_income_level.110001-plus")),
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

    conn.execute(
        "INSERT INTO meta VALUES ('fetched_at', ?)",
        (datetime.datetime.now(datetime.timezone.utc).isoformat(),),
    )
    conn.execute("INSERT INTO meta VALUES ('scorecard_data_year', ?)", (scorecard_data_year,))
    conn.execute("INSERT INTO meta VALUES ('schema_version', '1')")
    conn.commit()
    conn.close()


def _sum_or_none(a, b):
    if a is None or b is None:
        return None
    return int(a) + int(b)


def _first_not_none(*values):
    for v in values:
        if v is not None:
            return v
    return None


# College Scorecard's institution-level `latest.academics.program_percentage.*`
# field suffixes (the PCIPnn family in the raw data dictionary) map to 2-digit
# CIP family codes. This is the full standard set Scorecard publishes.
#
# NOTE: these suffix spellings are transcribed from the College Scorecard data
# dictionary. A handful of the less-common ones are best-effort and should be
# verified against the live API response the first time `refresh-data` is
# actually run against real data — any suffix the API does not recognise is
# simply absent from the response (Scorecard ignores unknown `fields` entries
# rather than erroring), so a wrong spelling degrades to a missing CIP family
# rather than a failed refresh. `_fields_string()` below is generated from this
# table, so a suffix added here is automatically requested from the API — the
# two can never drift apart again.
_PROGRAM_PERCENTAGE_TO_CIP2 = {
    "agriculture": "01",
    "resources": "03",
    "architecture": "04",
    "ethnic_cultural_gender": "05",
    "communication": "09",
    "communications_technology": "10",
    "computer": "11",
    "personal_culinary": "12",
    "education": "13",
    "engineering": "14",
    "engineering_technology": "15",
    "language": "16",
    "family_consumer_science": "19",
    "legal": "22",
    "english": "23",
    "humanities": "24",
    "library": "25",
    "biological": "26",
    "mathematics": "27",
    # Scorecard's "military" percentage covers CIP 29 (Military Technologies and
    # Applied Sciences); CIP 28 (Military Science / ROTC) has no separate
    # program_percentage field. Verify against live data.
    "military": "29",
    "multidiscipline": "30",
    "parks_recreation_fitness": "31",
    "philosophy_religious": "38",
    "theology_religious_vocation": "39",
    "physical_science": "40",
    "science_technology": "41",
    "psychology": "42",
    "security_law_enforcement": "43",
    "public_administration_social_service": "44",
    "social_science": "45",
    "construction": "46",
    "mechanic_repair_technology": "47",
    "precision_production": "48",
    "transportation": "49",
    "visual_performing": "50",
    "health": "51",
    "business_marketing": "52",
    "history": "54",
}

_INCOME_BRACKETS = ("0-30000", "30001-48000", "48001-75000", "75001-110000", "110001-plus")

_BASE_INSTITUTION_FIELDS = (
    "id",
    "school.name",
    "school.state",
    "school.operating",
    "latest.school.degrees_awarded.predominant",
    "latest.admissions.admission_rate.overall",
    "latest.admissions.sat_scores.25th_percentile.critical_reading",
    "latest.admissions.sat_scores.25th_percentile.math",
    "latest.admissions.sat_scores.75th_percentile.critical_reading",
    "latest.admissions.sat_scores.75th_percentile.math",
    "latest.student.size",
    "latest.cost.avg_net_price.overall",
    # Field-of-study data is NOT a separate endpoint (an earlier version of this
    # script assumed `/schools/fieldofstudy` existed -- it returns 404). It is
    # nested per-institution on the main /schools endpoint instead, as a full
    # array of program records. Verified live 2026-09: requesting a sub-field
    # path here (e.g. "...cip_4_digit.earnings") silently drops nested keys
    # deeper than credential/counts, so we request the whole array unfiltered
    # and flatten it ourselves in `extract_field_of_study_records`.
    "latest.programs.cip_4_digit",
)

# Real earnings windows Scorecard reports, tried in order (some programs only
# report a subset). Debt is intentionally not extracted: nothing in this app's
# scoring reads median_debt (grep confirms it's stored but never scored), and
# the live debt payload's shape varies per program (parent_plus/staff_grad_plus
# breakdowns rather than a single median), so it isn't worth the parsing
# complexity for a field with zero downstream consumers.
_EARNINGS_WINDOWS = ("1_yr", "4_yr", "5_yr")


def institution_fields_string() -> str:
    """Build the Scorecard `fields` query value.

    Derived from `_PROGRAM_PERCENTAGE_TO_CIP2` and `_INCOME_BRACKETS` so that
    every field `build_database` parses is actually requested from the API.
    """
    fields = list(_BASE_INSTITUTION_FIELDS)
    fields += [
        f"latest.academics.program_percentage.{suffix}"
        for suffix in _PROGRAM_PERCENTAGE_TO_CIP2
    ]
    for sector in ("public", "private"):
        fields += [
            f"latest.cost.net_price.{sector}.by_income_level.{bracket}"
            for bracket in _INCOME_BRACKETS
        ]
    return ",".join(fields)


_MAX_ATTEMPTS = 3


def _get_with_retry(url: str, params: dict) -> dict:
    """GET with a simple exponential backoff on 429/5xx responses."""
    last_exc = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = httpx.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status != 429 and status < 500:
                raise
            last_exc = exc
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(2 ** attempt)
    raise last_exc


def fetch_institutions(api_key: str) -> list[dict]:
    fields = institution_fields_string()
    results = []
    page = 0
    while True:
        data = _get_with_retry(
            "https://api.data.gov/ed/collegescorecard/v1/schools",
            {
                "api_key": api_key, "fields": fields, "per_page": 100, "page": page,
                "school.operating": 1, "latest.school.degrees_awarded.predominant": 3,
            },
        )
        results.extend(data["results"])
        if len(results) >= data["metadata"]["total"]:
            break
        page += 1
    return results


def _normalize_cip4(code: str) -> str:
    """Scorecard's cip_4_digit `code` is a bare 4-digit string (e.g. "0301"),
    a 2-digit CIP family plus two more digits -- not the full 6-digit official
    CIP code. Dot-separate it to "03.01" for consistent, matchable storage."""
    return f"{code[:2]}.{code[2:]}" if len(code) == 4 else code


def _best_effort_earnings(earnings: dict | None) -> float | None:
    if not earnings:
        return None
    for window in _EARNINGS_WINDOWS:
        value = (earnings.get(window) or {}).get("overall_median_earnings")
        if value is not None:
            return value
    return None


def extract_field_of_study_records(institution_records: list[dict]) -> list[dict]:
    """Flatten each institution's nested `latest.programs.cip_4_digit` array
    into the flat per-program record shape `build_database` expects, keeping
    only bachelor's-level programs (credential.level == 3 -- the only level
    this app scores)."""
    records = []
    for rec in institution_records:
        for program in rec.get("latest.programs.cip_4_digit") or []:
            if (program.get("credential") or {}).get("level") != 3:
                continue
            counts = program.get("counts") or {}
            records.append({
                "unitid": rec["id"],
                "cipcode": _normalize_cip4(program.get("code", "")),
                "credlev": 3,
                "counts.ipeds_count": _first_not_none(
                    counts.get("ipeds_awards2"), counts.get("ipeds_awards1")
                ),
                "earnings.median": _best_effort_earnings(program.get("earnings")),
                "debt.median": None,
            })
    return records


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    key = os.environ["COLLEGE_SCORECARD_API_KEY"]
    institutions = fetch_institutions(key)
    field_of_study = extract_field_of_study_records(institutions)
    build_database(institutions, field_of_study, "scorecard.sqlite", scorecard_data_year="2023-24")
    print(f"Wrote scorecard.sqlite with {len(institutions)} institutions, {len(field_of_study)} field-of-study rows")
