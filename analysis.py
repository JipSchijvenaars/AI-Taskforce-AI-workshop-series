"""Analysis: straight-line distance, the end-to-end orchestration
(``run_analysis``), and - from phase 4 - the rule-based competition
assessment.
"""

from __future__ import annotations

import math
from datetime import datetime

from osm import CATEGORY_LABELS, find_venues, geocode

EARTH_RADIUS_M = 6_371_000.0
DEFAULT_RADIUS_M = 1000
MAX_RESULTS = 5


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (straight-line) distance between two points, in metres.

    Plain Euclidean distance on lat/lon degrees would be wrong; on a ~1 km
    scale haversine is accurate to well under a metre, which is plenty here.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def meters(value: float | None) -> str:
    """Format a distance for display: rounded to the nearest 10 m, or '-'."""
    if value is None:
        return "-"
    return f"{int(round(value / 10.0) * 10)} m"


def run_analysis(
    address: str, category: str, radius_m: int = DEFAULT_RADIUS_M
) -> dict:
    """Geocode the address, find nearby venues of ``category``, and return a
    plain dict with everything the UI and the report need.

    Raises ``AddressNotFound`` / ``GeocodingError`` / ``OverpassError`` from
    the ``osm`` module on failure.
    """
    geo = geocode(address)
    venues = find_venues(geo.lat, geo.lon, category, radius_m)

    rows = [
        {
            "name": v.name,
            "kind": v.kind,
            "osm_type": v.osm_type,
            "website": v.website,
            "distance_m": haversine_m(geo.lat, geo.lon, v.lat, v.lon),
        }
        for v in venues
    ]
    rows.sort(key=lambda r: r["distance_m"])

    closest = rows[0]["distance_m"] if rows else None
    return {
        "address_input": address,
        "address_resolved": geo.display_name,
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, category),
        "radius_m": radius_m,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_within_radius": len(rows),
        "closest_distance_m": closest,
        "fewer_than_5": len(rows) < MAX_RESULTS,
        "matches": rows[:MAX_RESULTS],
        "assessment": None,  # filled in phase 4 (rule-based)
        "ai_narrative": None,  # optional extension, not built
    }
