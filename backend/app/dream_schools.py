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
