"""Asteroid picture lookup for Near Earth Explorer (M3). Async, built on httpx like the backend.

    from asteroid_image import get_asteroid_image, get_asteroid_images

    await get_asteroid_image(neo_item)          # a NeoWs item (dict) ...
    await get_asteroid_image("433 Eros (A898 PA)")   # ... or just the name
    await get_asteroid_images(list_of_neo_items)     # several at once (prefetch)

Always returns a dict the UI can show, and never raises:
    {
      "name", "source": "nasa" | "sample",
      "url", "title", "caption", "credit", "page",   # the picture for the detail page
      "sample_url",                                  # sample-asteroid.svg, the map icon
      "illustrative",                                # True -> UI must show `caption`
      "jpl_url",                                     # NeoWs nasa_jpl_url if you passed the item
    }

Pictures come from the NASA Image and Video Library (no API key). NASA only has photos of a few
named asteroids (Bennu, Eros, Ryugu, ...). Unnamed ones like "(2024 XY5)" get our own drawing.

Command line:  python asteroid_image.py "101955 Bennu (1999 RQ36)"
Call it from the backend only, never from the browser.
"""
import asyncio
import json
import math
import pathlib
import re
import sys
from typing import Any, Optional, Union

import httpx

SEARCH_URL = "https://images-api.nasa.gov/search"
HERE = pathlib.Path(__file__).parent
CACHE_FILE = HERE / "asteroid_image_cache.json"

STATIC_PREFIX = "/static/fallbacks"                   # M1: serve the static/ folder
DRAWING_URL = f"{STATIC_PREFIX}/asteroid.svg"          # dark backdrop, for the detail page
SAMPLE_ASTEROID_URL = f"{STATIC_PREFIX}/sample-asteroid.svg"  # transparent, for the map

# "(2024 XY5)" = unnamed provisional designation -> no photo exists. "433 Eros (A898 PA)" = named.
PROVISIONAL = re.compile(r"^\(?\s*\d{4}\s+[A-Z]{1,2}\d*\s*\)?$")

_CACHE: Optional[dict] = None


def _cache() -> dict:
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(CACHE_FILE.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            _CACHE = {}
    return _CACHE


def _save_cache() -> None:
    CACHE_FILE.write_text(json.dumps(_cache(), indent=2))


def search_name(name: str) -> Optional[str]:
    """Searchable name, or None for an unnamed rock. '433 Eros (A898 PA)' -> 'Eros'."""
    name = name.strip()
    if PROVISIONAL.match(name):
        return None
    base = re.sub(r"\(.*?\)", "", name).strip()
    base = re.sub(r"^\d+\s+", "", base)
    return base or None


def _unpack(asteroid: Union[str, dict]) -> tuple:
    if isinstance(asteroid, dict):
        return str(asteroid.get("name", "")), asteroid.get("nasa_jpl_url")
    return str(asteroid), None


def _is_relevant(name: str, item: dict) -> bool:
    tokens = [t for t in re.findall(r"[a-z0-9]+", name.lower()) if len(t) > 1]
    if not tokens:
        return False
    data = item["data"][0]
    haystack = (data.get("title", "") + " " + " ".join(data.get("keywords", []))).lower()
    return sum(t in haystack for t in tokens) >= math.ceil(0.6 * len(tokens))


def _sample() -> dict:
    return {
        "source": "sample",
        "url": DRAWING_URL,
        "title": "Illustration of an asteroid",
        "caption": "Illustration, not a photo. No photo of this asteroid exists.",
        "credit": "Near Earth Explorer",
        "page": None,
        "sample_url": SAMPLE_ASTEROID_URL,
        "illustrative": True,
    }


async def _search(client: httpx.AsyncClient, query: str) -> list:
    params = {"q": query, "media_type": "image", "page_size": 10}
    for attempt in range(2):                         # one retry on timeout
        try:
            r = await client.get(SEARCH_URL, params=params)
            r.raise_for_status()
            return r.json()["collection"]["items"]
        except httpx.TimeoutException:
            if attempt == 1:
                raise
    return []


async def _best_url(client: httpx.AsyncClient, thumb: str) -> str:
    """NASA serves ~thumb, ~small, ~medium, ~large, ~orig. Use medium when it exists."""
    if "~thumb" not in thumb:
        return thumb
    medium = thumb.replace("~thumb", "~medium")
    try:
        if (await client.head(medium)).is_success:
            return medium
    except httpx.HTTPError:
        pass
    return thumb


async def _photo(client: httpx.AsyncClient, item: dict) -> dict:
    data = item["data"][0]
    return {
        "source": "nasa",
        "url": await _best_url(client, item["links"][0]["href"]),
        "title": data.get("title", ""),
        "caption": f"{data.get('title', '')} (NASA)",
        "credit": "NASA",
        "page": f"https://images.nasa.gov/details/{data['nasa_id']}",
        "sample_url": SAMPLE_ASTEROID_URL,
        "illustrative": False,
    }


async def get_asteroid_image(asteroid: Union[str, dict],
                             client: Optional[httpx.AsyncClient] = None) -> dict:
    name, jpl_url = _unpack(asteroid)
    extra = {"name": name, "jpl_url": jpl_url}
    if name in _cache():
        return {**_cache()[name], **extra}

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=10, follow_redirects=True)
    try:
        result = None
        found = search_name(name)
        if found:                                     # unnamed rocks skip the search entirely
            for item in await _search(client, f"{found} asteroid"):
                if item.get("links") and _is_relevant(found, item):
                    result = await _photo(client, item)
                    break
        result = result or _sample()
    except (httpx.HTTPError, KeyError, ValueError):
        return {**_sample(), **extra}                 # network trouble: show the drawing, do not cache
    finally:
        if own_client:
            await client.aclose()

    _cache()[name] = result
    _save_cache()
    return {**result, **extra}


async def get_asteroid_images(asteroids: list, concurrency: int = 3) -> list:
    """Look up many asteroids at once, at most `concurrency` NASA calls in flight."""
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        async def one(a: Any) -> dict:
            async with sem:
                return await get_asteroid_image(a, client)
        return await asyncio.gather(*(one(a) for a in asteroids))


try:  # lets M1 mount it with app.include_router(router)
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/api/asteroid-image")
    async def asteroid_image_endpoint(name: str):
        return await get_asteroid_image(name)
except ImportError:
    pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(asyncio.run(get_asteroid_image(sys.argv[1])), indent=2))
    else:
        print(__doc__)
