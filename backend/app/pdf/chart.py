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
