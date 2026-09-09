"""Analysis: straight-line distance, the end-to-end orchestration
(``run_analysis``), and - from phase 4 - the rule-based competition
assessment.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
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
    """Format a distance for display: whole metres, or '-' if unknown."""
    if value is None:
        return "-"
    return f"{round(value)} m"


@dataclass(frozen=True)
class Assessment:
    level: str  # "lower" | "moderate" | "higher"
    summary: str  # a short paragraph that quotes the retrieved numbers
    proximity_note: str | None  # extra warning if a competitor is very close


def assess(
    category_label: str, total_within_radius: int, closest_distance_m: float | None
) -> Assessment:
    """Transparent, rule-based competition indication (no LLM).

    Thresholds from the assignment: 0-1 = lower, 2-4 = moderate, 5+ = higher
    direct competition; plus a note if the nearest competitor is under 250 m.
    """
    cat = category_label.lower()

    if total_within_radius <= 1:
        level, verdict = "lower", "Observed direct competition is limited."
    elif total_within_radius <= 4:
        level, verdict = "moderate", "Several direct competitors are already present."
    else:
        level, verdict = "higher", "The area is already served by many direct competitors."

    if total_within_radius == 0:
        summary = (
            f"Indicative competition: lower. The OpenStreetMap query found no mapped "
            f"{cat} venues within 1 km of the address. Local demand and supply still "
            f"need to be checked on the ground before making a location decision."
        )
    else:
        summary = (
            f"Indicative competition: {level}. The OpenStreetMap query found "
            f"{total_within_radius} mapped {cat} venue(s) within 1 km of the address; "
            f"the nearest is about {meters(closest_distance_m)} away. {verdict} "
            f"Validate with local field research before making a location decision."
        )

    proximity_note = None
    if closest_distance_m is not None and closest_distance_m < 250:
        proximity_note = (
            f"A mapped {cat} venue sits about {meters(closest_distance_m)} away - "
            f"a direct competitor is very nearby."
        )

    return Assessment(level=level, summary=summary, proximity_note=proximity_note)


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
    category_label = CATEGORY_LABELS.get(category, category)
    assessment = assess(category_label, len(rows), closest)

    return {
        "address_input": address,
        "address_resolved": geo.display_name,
        "category": category,
        "category_label": category_label,
        "radius_m": radius_m,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_within_radius": len(rows),
        "closest_distance_m": closest,
        "fewer_than_5": len(rows) < MAX_RESULTS,
        "matches": rows[:MAX_RESULTS],
        "assessment": asdict(assessment),
        "ai_narrative": None,  # optional extension, not built
    }
