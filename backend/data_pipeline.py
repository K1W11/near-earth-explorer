"""Ingest and cache Near Earth Explorer's upstream astronomy datasets.

This module owns the external-data boundary for the FastAPI application:
NASA's Near Earth Object Web Service (NeoWs) supplies asteroid close-approach
records, and CelesTrak supplies active-satellite Two-Line Element (TLE) sets
that are later propagated by ``look_angles.py`` using SGP4.

Both feeds are cached in process memory for one hour. Reusing the normalized
payloads avoids redundant outbound requests and helps protect NASA and
CelesTrak rate limits during hackathon judging, when multiple frontend clients
may refresh the same map data concurrently. A per-dataset asynchronous lock
collapses simultaneous cache misses so only one upstream request is made per
feed at a time. The cache is process-local; multi-worker deployments should
use a shared cache if cross-worker consistency is required.

Public API:
    ``fetch_asteroids`` returns NEO records sorted by nearest miss distance.
    ``fetch_active_satellites`` returns CelesTrak records containing a name
    and the two TLE lines used by the orbital look-angle endpoint.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Dict, List, TypeVar

import httpx

CACHE_TTL = 3600
"""Maximum age, in seconds, for any cached NASA or CelesTrak payload."""

NASA_FEED_URL = "https://api.nasa.gov/neo/rest/v1/feed"
"""NASA NeoWs close-approach feed endpoint."""

CELESTRAK_ACTIVE_TLE_URL = (
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
)
"""CelesTrak endpoint that returns active satellites in three-line TLE format."""

_cache: Dict[str, Dict[str, Any]] = {}
"""Dataset cache: keys map to ``{"timestamp": float, "data": payload}`` entries."""

_cache_locks: Dict[str, asyncio.Lock] = {}
"""Per-dataset locks used to prevent duplicate upstream requests on cache misses."""

_Payload = TypeVar("_Payload")


def _lock_for(cache_key: str) -> asyncio.Lock:
    """Return the lock associated with one cache key.

    Separate locks let NASA and CelesTrak requests proceed independently while
    requests for the same expired feed share one refresh operation.
    """
    lock = _cache_locks.get(cache_key)
    if lock is None:
        lock = asyncio.Lock()
        _cache_locks[cache_key] = lock
    return lock


async def _cached_fetch(
    cache_key: str,
    fetch: Callable[[], Awaitable[_Payload]],
) -> _Payload:
    """Return a fresh cache entry or fetch, normalize, and cache new data.

    Cache timestamps use wall-clock ``time.time()`` as part of the public
    in-memory record format. The cache is checked both before and after taking
    the key lock: the second check lets concurrent callers reuse the result
    produced by the first caller instead of issuing a burst of API requests.
    Exceptions from the upstream request or response parser are not cached.
    """
    entry = _cache.get(cache_key)
    if entry is not None and time.time() - entry["timestamp"] < CACHE_TTL:
        return entry["data"]

    async with _lock_for(cache_key):
        entry = _cache.get(cache_key)
        if entry is not None and time.time() - entry["timestamp"] < CACHE_TTL:
            return entry["data"]

        payload = await fetch()
        _cache[cache_key] = {
            "timestamp": time.time(),
            "data": payload,
        }
        return payload


def _parse_asteroid_feed(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten and normalize NASA's date-keyed NeoWs feed.

    NeoWs returns a ``near_earth_objects`` mapping whose values are lists of
    asteroids, grouped by close-approach date. For each asteroid, this parser
    extracts its first approach record, converts the API's string-valued
    distance and velocity measurements to floats, converts maximum estimated
    diameter to kilometers rounded to three decimal places, and sorts the
    flattened output by miss distance so index zero is the closest approach.
    """
    date_groups = payload.get("near_earth_objects")
    if not isinstance(date_groups, dict):
        raise ValueError("NASA NeoWs response is missing near_earth_objects")

    asteroids: List[Dict[str, Any]] = []
    for objects_on_date in date_groups.values():
        if not isinstance(objects_on_date, list):
            continue

        for asteroid in objects_on_date:
            if not isinstance(asteroid, dict):
                continue
            approaches = asteroid.get("close_approach_data")
            if not isinstance(approaches, list) or not approaches:
                continue

            approach = approaches[0]
            if not isinstance(approach, dict):
                continue

            miss_distance = approach.get("miss_distance", {}).get("kilometers")
            relative_velocity = approach.get("relative_velocity", {}).get(
                "kilometers_per_hour"
            )
            diameter_km = (
                asteroid.get("estimated_diameter", {})
                .get("kilometers", {})
                .get("estimated_diameter_max")
            )
            if miss_distance is None or relative_velocity is None or diameter_km is None:
                continue

            close_approach_date = approach.get("close_approach_date_full")
            if close_approach_date is None:
                close_approach_date = approach.get("close_approach_date")

            asteroids.append(
                {
                    "id": str(asteroid.get("id", "")),
                    "name": asteroid.get("name", "Unknown object"),
                    "estimated_diameter_km": round(float(diameter_km), 3),
                    "is_potentially_hazardous_asteroid": bool(
                        asteroid.get("is_potentially_hazardous_asteroid", False)
                    ),
                    "close_approach_date_full": close_approach_date,
                    "miss_distance_km": float(miss_distance),
                    "relative_velocity_kmh": float(relative_velocity),
                }
            )

    asteroids.sort(key=lambda asteroid: asteroid["miss_distance_km"])
    return asteroids


async def fetch_asteroids(nasa_api_key: str = "DEMO_KEY") -> List[Dict[str, Any]]:
    """Fetch and return the upcoming NeoWs asteroid feed.

    Args:
        nasa_api_key: NASA API key passed as the NeoWs ``api_key`` query
            parameter. The default ``DEMO_KEY`` supports local evaluation with
            NASA's lower shared request quota.

    Returns:
        A list of normalized asteroid records in ascending miss-distance order.
        Each record includes ``id``, ``name``, ``estimated_diameter_km``,
        ``is_potentially_hazardous_asteroid``, ``close_approach_date_full``,
        ``miss_distance_km``, and ``relative_velocity_kmh``.

    Raises:
        httpx.HTTPError: If NASA cannot be reached or returns a non-success
            HTTP status. ``raise_for_status`` ensures error responses are not
            mistaken for valid feed data.
        ValueError: If the successful response does not contain NeoWs's
            expected ``near_earth_objects`` mapping.
    """
    async def request_and_parse() -> List[Dict[str, Any]]:
        """Request today's NeoWs feed and normalize its JSON response."""
        today_str = time.strftime("%Y-%m-%d", time.gmtime())
        params = {
            "start_date": today_str,
            "api_key": nasa_api_key,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(NASA_FEED_URL, params=params)
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError("NASA NeoWs returned a non-object JSON response")
        return _parse_asteroid_feed(payload)

    return await _cached_fetch("asteroids", request_and_parse)


def _parse_active_satellites(document: str) -> List[Dict[str, str]]:
    """Parse CelesTrak's name/line-1/line-2 records.

    The text feed is made of repeating three-line blocks: satellite name,
    TLE line 1 (prefixed ``1 ``), and TLE line 2 (prefixed ``2 ``). Empty lines
    are ignored before block parsing. Invalid or incomplete blocks are skipped
    because they cannot be used by SGP4; valid records retain the exact TLE
    lines returned by CelesTrak.
    """
    lines = [line.strip() for line in document.splitlines() if line.strip()]
    satellites: List[Dict[str, str]] = []
    for index in range(0, len(lines) - 2, 3):
        name, tle1, tle2 = lines[index : index + 3]
        if not name or not tle1.startswith("1 ") or not tle2.startswith("2 "):
            continue
        satellites.append(
            {
                "name": name.removeprefix("0 ").strip(),
                "tle1": tle1,
                "tle2": tle2,
            }
        )
    return satellites


async def fetch_active_satellites() -> List[Dict[str, str]]:
    """Fetch and return CelesTrak's active satellite TLE catalog.

    Returns:
        Satellite mappings with the keys ``name``, ``tle1``, and ``tle2``.
        These TLE lines are consumed by the FastAPI observer route and passed
        to ``look_angles.calculate_look_angles`` for SGP4 propagation.

    Raises:
        httpx.HTTPError: If CelesTrak cannot be reached or returns a non-success
            HTTP status. Failed responses are not cached.
    """
    async def request_and_parse() -> List[Dict[str, str]]:
        """Download the active TLE text document and parse its three-line blocks."""
        headers = {
            "User-Agent": "NearEarthExplorer/1.0 (educational hackathon project)"
        }
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            response = await client.get(CELESTRAK_ACTIVE_TLE_URL)
            response.raise_for_status()
            document = response.text
        return _parse_active_satellites(document)

    return await _cached_fetch("satellites", request_and_parse)


def cache_status() -> Dict[str, int]:
    """Return current cache-entry ages in seconds for health reporting.

    Only cache keys and integer ages are exposed; cached object payloads and
    API credentials are never included in the health response.
    """
    now = time.time()
    return {
        key: max(0, int(now - entry["timestamp"]))
        for key, entry in _cache.items()
    }


async def get_near_earth_objects(
    api_key: str | None = None,
) -> List[Dict[str, Any]]:
    """Compatibility wrapper for callers using the earlier pipeline name."""
    return await fetch_asteroids(api_key or "DEMO_KEY")


async def get_active_satellites() -> List[Dict[str, str]]:
    """Compatibility wrapper for callers using the earlier pipeline name."""
    return await fetch_active_satellites()
