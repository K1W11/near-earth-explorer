"""External data ingestion and process-local TTL caching for Near Earth Explorer.

The API gateway uses this module to retrieve NASA NeoWs close-approach data and
CelesTrak active satellite TLEs. A one-hour in-memory cache reduces repeated
outbound requests and protects shared public API quotas during live judging;
the cache is intentionally process-local and can be replaced by shared storage
if the service later scales across multiple workers or hosts.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

import httpx

CACHE_TTL_SECONDS = 3600
"""Time-to-live applied to NASA and CelesTrak responses."""

NASA_FEED_URL = "https://api.nasa.gov/neo/rest/v1/feed"
CELESTRAK_ACTIVE_TLE_URL = (
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
)

_T = TypeVar("_T")
_cache: dict[str, tuple[float, Any]] = {}
_cache_locks: dict[str, asyncio.Lock] = {}


def _lock_for(key: str) -> asyncio.Lock:
    """Return the per-key lock used to collapse concurrent cache misses."""
    lock = _cache_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _cache_locks[key] = lock
    return lock


async def _get_cached(
    key: str,
    fetch: Callable[[], Awaitable[_T]],
    ttl_seconds: int = CACHE_TTL_SECONDS,
) -> _T:
    """Return cached data when fresh, otherwise fetch once and refresh the key."""
    now = time.monotonic()
    cached = _cache.get(key)
    if cached is not None and now - cached[0] < ttl_seconds:
        return cached[1]

    # The second cache check prevents parallel requests from all fetching the
    # same large upstream dataset after the same expiry.
    async with _lock_for(key):
        now = time.monotonic()
        cached = _cache.get(key)
        if cached is not None and now - cached[0] < ttl_seconds:
            return cached[1]
        value = await fetch()
        _cache[key] = (time.monotonic(), value)
        return value


def _parse_neo_feed(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten NeoWs' date-keyed feed and sort objects by closest approach.

    NASA groups NeoWs records by close-approach date. The browser and Gemini
    tools need one consistent list, so this parser extracts the user-facing
    fields from every date bucket, converts miss distance from the API's
    string-valued kilometers, and sorts ascending by that distance.
    """
    objects: list[dict[str, Any]] = []
    date_groups = payload.get("near_earth_objects", {})
    if not isinstance(date_groups, dict):
        raise ValueError("NASA NeoWs response did not contain a valid object collection")

    for dated_objects in date_groups.values():
        if not isinstance(dated_objects, list):
            continue
        for asteroid in dated_objects:
            if not isinstance(asteroid, dict):
                continue
            approaches = asteroid.get("close_approach_data") or []
            if not approaches:
                continue
            approach = approaches[0]
            miss_distance = approach.get("miss_distance", {}).get("kilometers")
            velocity = approach.get("relative_velocity", {}).get("kilometers_per_second")
            if miss_distance is None:
                continue

            diameters = asteroid.get("estimated_diameter", {}).get("kilometers", {})
            objects.append(
                {
                    "id": str(asteroid.get("id", "")),
                    "name": asteroid.get("name", "Unknown object"),
                    "close_approach_date": approach.get("close_approach_date"),
                    "miss_distance_km": float(miss_distance),
                    "relative_velocity_kps": (
                        float(velocity) if velocity is not None else None
                    ),
                    "estimated_diameter_km": {
                        "min": diameters.get("estimated_diameter_min"),
                        "max": diameters.get("estimated_diameter_max"),
                    },
                    "is_potentially_hazardous": bool(
                        asteroid.get("is_potentially_hazardous_asteroid", False)
                    ),
                    "nasa_jpl_url": asteroid.get("nasa_jpl_url"),
                }
            )

    objects.sort(key=lambda item: item["miss_distance_km"])
    return objects


async def _fetch_neo_feed(api_key: str) -> list[dict[str, Any]]:
    """Fetch the upcoming seven-day NeoWs feed and return normalized records."""
    start_date = datetime.now(timezone.utc).date()
    # NeoWs accepts windows of at most seven days; using start plus six days
    # includes exactly seven UTC calendar dates, avoiding a rejected 8-day span.
    end_date = start_date + timedelta(days=6)
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "api_key": api_key,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(NASA_FEED_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("NASA NeoWs returned an unexpected response shape")
    return _parse_neo_feed(payload)


async def get_near_earth_objects(api_key: str | None = None) -> list[dict[str, Any]]:
    """Return cached upcoming NEOs sorted by ascending miss distance."""
    resolved_key = api_key or os.getenv("NASA_API_KEY", "DEMO_KEY") or "DEMO_KEY"
    # A key-specific cache avoids serving a DEMO_KEY response when an operator
    # changes to a higher-quota key while the process remains alive.
    return await _get_cached(
        f"neo-feed:{resolved_key}",
        lambda: _fetch_neo_feed(resolved_key),
    )


async def fetch_asteroids() -> list[dict[str, Any]]:
    """Fetch normalized seven-day asteroid data for the FastAPI gateway.

    This public name keeps the route layer independent of cache implementation
    details; the underlying NeoWs request still uses the shared one-hour TTL.
    """
    return await get_near_earth_objects()


def _parse_celestrak_tles(document: str) -> list[dict[str, str]]:
    """Parse CelesTrak's three-line name/TLE records into API-ready objects."""
    lines = [line.strip() for line in document.splitlines() if line.strip()]
    satellites: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        # CelesTrak's TLE format is name, line 1, line 2; accepting either a
        # plain name or a "0 NAME" label tolerates both common text variants.
        if not lines[index].startswith("1 "):
            index += 1
            continue
        if index + 1 >= len(lines) or not lines[index + 1].startswith("2 "):
            index += 1
            continue

        raw_name = lines[index - 1] if index > 0 else "Unknown satellite"
        name = raw_name[2:].strip() if raw_name.startswith("0 ") else raw_name
        line1, line2 = lines[index], lines[index + 1]
        satellites.append(
            {
                "name": name or "Unknown satellite",
                "norad_id": line1[2:7].strip(),
                "tle_line1": line1,
                "tle_line2": line2,
            }
        )
        index += 2

    # Sorting by name gives the frontend a stable presentation order even
    # though the upstream group's order can change as satellites are added.
    satellites.sort(key=lambda item: item["name"].casefold())
    return satellites


async def _fetch_active_satellites() -> list[dict[str, str]]:
    """Download and parse CelesTrak's active satellite TLE group."""
    headers = {"User-Agent": "NearEarthExplorer/1.0 (educational hackathon project)"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        response = await client.get(CELESTRAK_ACTIVE_TLE_URL)
        response.raise_for_status()
    return _parse_celestrak_tles(response.text)


async def get_active_satellites() -> list[dict[str, str]]:
    """Return the cached CelesTrak active group as normalized TLE records."""
    return await _get_cached("celestrak:active-tles", _fetch_active_satellites)


async def fetch_active_satellites() -> list[dict[str, str]]:
    """Fetch normalized active TLE records through the shared cache."""
    return await get_active_satellites()


def cache_status() -> dict[str, int]:
    """Expose cache age only (never cached payloads or credentials) for health."""
    now = time.monotonic()
    return {
        key: max(0, int(now - stored_at))
        for key, (stored_at, _value) in _cache.items()
    }
