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
    return any(k in (interests.get("raw_text") or "").lower() for k in OCEAN_KEYWORDS)


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
