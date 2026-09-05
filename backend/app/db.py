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
    # Explicit ordering: tie-breaking downstream (pipeline sorting, dream-school
    # merging) must not depend on unordered SQL row order.
    query += " ORDER BY unit_id"
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    if cip_2digit:
        # Per the design spec, program availability is "checked at cip_4digit
        # first, falls back to cip_2digit family". A school is eligible if it
        # has bachelor's-level graduates in ANY 4-digit CIP inside the family
        # (field_of_study), OR it reports a non-zero share of degrees in that
        # CIP-2 family (cip2_percentages). The OR keeps eligibility working even
        # where the institution-level program_percentage mapping has gaps.
        eligible_ids = {
            r["unit_id"] for r in conn.execute(
                "SELECT DISTINCT unit_id FROM field_of_study "
                "WHERE cip_code LIKE ? AND credential_level = 'bachelors' AND graduates > 0",
                (f"{cip_2digit}.%",),
            ).fetchall()
        }
        eligible_ids |= {
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
