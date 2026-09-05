import sqlite3
import datetime
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

    conn.execute("INSERT INTO meta VALUES ('fetched_at', ?)", (datetime.datetime.utcnow().isoformat(),))
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
