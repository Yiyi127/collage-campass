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
