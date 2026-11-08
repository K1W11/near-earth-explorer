"""Story lookup for narration: real facts -> Gemini story -> disk cache.

``get_story`` never raises. If facts can't be found or Gemini fails it returns
a generic sentence, so audio still works. Only *generated* stories are cached,
so a transient Gemini outage doesn't freeze the placeholder in place. Caching
matters twice over: Gemini wording varies run to run, and different wording
would mean a new audio hash (a new ElevenLabs charge) on every click.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from audio import voice
from data_pipeline import fetch_active_satellites, fetch_asteroids
from gemini_service import generate_story
from look_angles import calculate_altitude_km

logger = logging.getLogger("near_earth_explorer")

_locks: dict[str, asyncio.Lock] = {}


def fallback_story(name: str) -> str:
    return (
        f"Now targeting {name}. This space target is actively "
        "monitored by Near Earth Explorer."
    )


def _norm(name: str) -> str:
    return re.sub(r"[()\s]+", " ", name).strip().casefold()


def _cache_file():
    return voice.AUDIO_DIR / "stories.json"


def _read_cache() -> dict[str, str]:
    try:
        return json.loads(_cache_file().read_text())
    except (OSError, ValueError):
        return {}


def _write_cache(cache: dict[str, str]) -> None:
    voice.AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _cache_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2))
    tmp.replace(_cache_file())  # atomic, like the mp3 files


async def _asteroid_facts(name: str) -> dict[str, Any] | None:
    for asteroid in await fetch_asteroids():
        if _norm(asteroid["name"]) == _norm(name):
            return {
                "name": asteroid["name"],
                "estimated_diameter_km": asteroid["estimated_diameter_km"],
                "potentially_hazardous": asteroid["is_potentially_hazardous_asteroid"],
                "closest_approach": asteroid["close_approach_date_full"],
                "miss_distance_km": round(asteroid["miss_distance_km"]),
                "speed_km_per_hour": round(asteroid["relative_velocity_kmh"]),
            }
    return None


async def _satellite_facts(name: str) -> dict[str, Any] | None:
    for satellite in await fetch_active_satellites():
        if _norm(satellite["name"]) == _norm(name):
            altitude = calculate_altitude_km(satellite["tle1"], satellite["tle2"])
            return {"name": satellite["name"], "altitude_km_right_now": round(altitude)}
    return None


async def get_story(name: str, object_type: str) -> str:
    """Return the story to narrate for one map object (see module docstring)."""
    key = f"{object_type}:{_norm(name)}"
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:  # simultaneous clicks trigger one Gemini call
        cached = _read_cache().get(key)
        if cached:
            return cached
        try:
            lookup = _asteroid_facts if object_type == "asteroid" else _satellite_facts
            facts = await lookup(name)
            if facts is None:
                logger.info("No facts found for %s %r; using fallback story", object_type, name)
                return fallback_story(name)
            story = await generate_story(object_type, facts)
        except Exception as error:  # data feeds, bad TLE, Gemini: never block audio
            logger.warning("Story generation failed for %r: %s", name, error)
            return fallback_story(name)
        cache = _read_cache()
        cache[key] = story
        _write_cache(cache)
        return story
