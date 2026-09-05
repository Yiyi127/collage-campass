from app.db import find_school_by_name


def resolve_dream_school(conn, name, required_state, required_budget):
    school = find_school_by_name(conn, name)
    # Three distinct exclusion causes, three distinct explanations -- "not found"
    # is a name/spelling problem for the counselor to check, while "closed" and
    # "no bachelor's degrees" are real facts about a school we did match.
    if school is None:
        return {"status": "excluded", "school": None,
                "reason": f"No school matching '{name}' was found in the College Scorecard "
                          f"data. Check the spelling or use the institution's full official name."}
    if not school["operating"]:
        return {"status": "excluded", "school": None,
                "reason": f"'{school['name']}' is recorded in College Scorecard as no longer "
                          f"operating, so it was left off the list. Verify with the school directly."}
    if not school["grants_bachelors"]:
        return {"status": "excluded", "school": None,
                "reason": f"'{school['name']}' does not predominantly award bachelor's degrees "
                          f"according to College Scorecard, so it was left off the list."}

    if required_state and school["state"] != required_state:
        return {"status": "exception", "school": school,
                "reason": f"You named this as a dream school, but it's in {school['state']}, "
                          f"which conflicts with the requirement to stay in {required_state}."}
    if required_budget is not None and school["net_price_overall"] and school["net_price_overall"] > required_budget:
        return {"status": "exception", "school": school,
                "reason": f"You named this as a dream school, but its average net price of "
                          f"${school['net_price_overall']:,.0f} exceeds the stated budget of "
                          f"${required_budget:,.0f}."}

    return {"status": "included", "school": school, "reason": None}
