"""OpenStreetMap access: a shared cached HTTP session, Nominatim geocoding and
Overpass venue search.

All OSM traffic goes through one ``requests_cache`` session so that repeated
identical requests during development are served from a local SQLite file
instead of hitting the public servers again. Nominatim asks callers to stay
under ~1 request/second and to send an identifying User-Agent; both are
handled here.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import requests
import requests_cache

# Identify the app to the OSM servers, with a contact address (their policy).
USER_AGENT = "horeca-competition-lens/0.1 (jip@schijvenaars.name)"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Primary endpoint first; the second is a mirror used only as a fallback.
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
_CACHE_PATH = Path(__file__).resolve().parent / ".cache" / "osm_cache"
_MIN_NOMINATIM_INTERVAL_S = 1.1
_NOMINATIM_TIMEOUT_S = 20
_OVERPASS_QUERY_TIMEOUT_S = 25  # goes inside the Overpass QL [timeout:...] setting
# The HTTP read timeout must comfortably exceed the QL timeout above, or we
# give up while the server is still computing. (connect, read) seconds.
_OVERPASS_TIMEOUT_S = (10, 90)

# One category maps to exactly one OSM tag filter. Deliberately strict: this
# excludes bar/pub/fast_food/guest_house/hostel so the count stays transparent
# and easy to explain. Noted as a limitation in the report.
CATEGORY_TAGS = {
    "cafe": '["amenity"="cafe"]',
    "restaurant": '["amenity"="restaurant"]',
    "hotel": '["tourism"="hotel"]',
}
CATEGORY_LABELS = {"cafe": "Café", "restaurant": "Restaurant", "hotel": "Hotel"}


class GeocodingError(Exception):
    """Nominatim could not be reached or returned something unusable."""


class AddressNotFound(GeocodingError):
    """Nominatim reached, but no location matched the address."""


class OverpassError(Exception):
    """Every Overpass endpoint failed or returned something unusable."""


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lon: float
    display_name: str  # Nominatim's normalised address - show this in the UI/report


@dataclass(frozen=True)
class Venue:
    name: str
    osm_type: str  # "node" | "way" | "relation"
    kind: str  # human label, e.g. "Restaurant"
    website: str | None
    lat: float
    lon: float


_session: requests_cache.CachedSession | None = None
_session_lock = threading.Lock()
_throttle_lock = threading.Lock()
_last_real_nominatim_call = 0.0


def get_session() -> requests_cache.CachedSession:
    """Return the process-wide cached session, creating it on first use."""
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:
                _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                _session = requests_cache.CachedSession(
                    cache_name=str(_CACHE_PATH),
                    backend="sqlite",
                    allowable_methods=("GET", "POST"),  # Overpass uses POST
                    allowable_codes=(200,),  # never cache 429/504/etc.
                    expire_after=timedelta(days=7),
                )
                _session.headers["User-Agent"] = USER_AGENT
    return _session


def _is_cached(session: requests_cache.CachedSession, prepared: requests.PreparedRequest) -> bool:
    try:
        return session.cache.contains(request=prepared)
    except Exception:
        return False


def _throttle_nominatim() -> None:
    """Sleep so that real Nominatim calls stay ~1s apart (cached calls skip this)."""
    global _last_real_nominatim_call
    with _throttle_lock:
        wait = _MIN_NOMINATIM_INTERVAL_S - (time.monotonic() - _last_real_nominatim_call)
        if wait > 0:
            time.sleep(wait)


def geocode(address: str) -> GeocodeResult:
    """Resolve a free-form address to coordinates via OpenStreetMap Nominatim.

    Raises ``AddressNotFound`` if nothing matches, ``GeocodingError`` on any
    network/parse problem.
    """
    global _last_real_nominatim_call

    address = (address or "").strip()
    if not address:
        raise AddressNotFound("No address entered.")

    session = get_session()
    params = {
        "q": address,
        "format": "jsonv2",
        "limit": 1,
        "addressdetails": 1,
    }
    prepared = session.prepare_request(requests.Request("GET", NOMINATIM_URL, params=params))

    if not _is_cached(session, prepared):
        _throttle_nominatim()

    try:
        response = session.send(prepared, timeout=_NOMINATIM_TIMEOUT_S)
        # Record the timestamp only for calls that actually hit the network.
        if not getattr(response, "from_cache", False):
            _last_real_nominatim_call = time.monotonic()
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise GeocodingError(f"Could not reach Nominatim: {exc}") from exc
    except ValueError as exc:  # invalid JSON
        raise GeocodingError("Nominatim returned an unexpected response.") from exc

    if not payload:
        raise AddressNotFound(
            f"No location found for {address!r}. Try adding a street number, "
            "postcode or city."
        )

    top = payload[0]
    try:
        return GeocodeResult(
            lat=float(top["lat"]),
            lon=float(top["lon"]),
            display_name=top.get("display_name", address),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError("Nominatim result was missing coordinates.") from exc


def _build_overpass_query(lat: float, lon: float, category: str, radius_m: int) -> str:
    tag_filter = CATEGORY_TAGS[category]
    # nwr = nodes + ways + relations; venues are often mapped as a building
    # (way) or a site (relation), not just a point.
    return (
        f"[out:json][timeout:{_OVERPASS_QUERY_TIMEOUT_S}];\n"
        f"nwr{tag_filter}(around:{radius_m},{lat},{lon});\n"
        f"out center tags;"
    )


def _parse_venues(elements: list[dict], kind_label: str) -> list[Venue]:
    venues: list[Venue] = []
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name:
            # Unnamed objects are skipped from both the list and the count so
            # the two stay consistent. Noted as a limitation in the report.
            continue

        if "lat" in el and "lon" in el:  # node
            point = el
        else:  # way / relation -> "out center" gives a computed centroid
            point = el.get("center") or {}
        try:
            plat, plon = float(point["lat"]), float(point["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        website = (
            tags.get("website")
            or tags.get("contact:website")
            or tags.get("url")
            or None
        )
        venues.append(
            Venue(
                name=name,
                osm_type=el.get("type", "node"),
                kind=kind_label,
                website=website,
                lat=plat,
                lon=plon,
            )
        )
    return venues


def find_venues(
    lat: float, lon: float, category: str, radius_m: int = 1000
) -> list[Venue]:
    """Return named OSM venues of ``category`` within ``radius_m`` of a point.

    ``category`` must be one of ``CATEGORY_TAGS`` ("cafe", "restaurant",
    "hotel"). Raises ``OverpassError`` if no endpoint answers usably.
    """
    if category not in CATEGORY_TAGS:
        raise ValueError(f"Unknown category: {category!r}")

    session = get_session()
    query = _build_overpass_query(lat, lon, category, radius_m)
    last_error: Exception | None = None

    for url in OVERPASS_URLS:
        try:
            response = session.post(url, data=query, timeout=_OVERPASS_TIMEOUT_S)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(1.0)  # brief backoff before trying the mirror
            continue

        remark = payload.get("remark", "") if isinstance(payload, dict) else ""
        if "timed out" in remark.lower() or "runtime error" in remark.lower():
            last_error = OverpassError(f"Overpass reported: {remark}")
            # Don't let a server-side timeout linger in the cache.
            try:
                session.cache.delete(response.cache_key)
            except Exception:
                pass
            continue

        return _parse_venues(payload.get("elements", []), CATEGORY_LABELS[category])

    raise OverpassError(
        f"Could not get data from Overpass ({last_error})."
    ) from last_error
