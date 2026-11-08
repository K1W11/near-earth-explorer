"""Satellite picture lookup for Near Earth Explorer (M3). Async, built on httpx like the backend.

    from satellite_image import get_satellite_image, get_satellite_images

    await get_satellite_image(sat)                # a pipeline dict {name, tle1, tle2} ...
    await get_satellite_image("HST")              # ... or just the CelesTrak name
    await get_satellite_images(list_of_sats)      # several at once (prefetch)

Always returns a dict the UI can show, and never raises:
    {
      "name", "source": "nasa" | "sample",
      "url", "title", "caption", "credit", "page",   # the picture for the detail page
      "sample_url",                                  # sample-satellite.svg, the map icon
      "illustrative",                                # True -> UI must show `caption`
      "norad_id", "info_url",                        # from tle1 when you pass the dict
    }

Pictures come from the NASA Image and Video Library (no API key). NASA has photos of its own
spacecraft (ISS, Hubble, Terra, Aqua, Landsat, ...). Commercial constellations like Starlink,
and anything NASA does not show, get our own drawing instead.

Pin the exact photo for a demo satellite by adding its NASA id to CURATED below (find the id in
the images.nasa.gov URL: https://images.nasa.gov/details/<id>).

Command line:  python satellite_image.py "HST"
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
CACHE_FILE = HERE / "satellite_image_cache.json"

STATIC_PREFIX = "/static/fallbacks"                      # M1: mount_images(app) serves this
DRAWING_URL = f"{STATIC_PREFIX}/satellite.svg"            # dark backdrop, for the detail page
SAMPLE_SATELLITE_URL = f"{STATIC_PREFIX}/sample-satellite.svg"  # transparent, for the map

# Hand-picked photos for the satellites you will demo: CelesTrak name (upper case) -> NASA id.
CURATED: dict = {}

# CelesTrak names are not what people write. Value = what to search NASA for.
ALIASES = {
    "ISS (ZARYA)": "International Space Station",
    "ISS (NAUKA)": "International Space Station",
    "ISS": "International Space Station",
    "HST": "Hubble Space Telescope",
    "FGST": "Fermi Gamma-ray Space Telescope",
    "CSS (TIANHE)": "Tiangong space station",
    "SUOMI NPP": "Suomi NPP",
}

# Constellations and junk NASA has no photos of: skip the search, show the drawing.
NO_PHOTO_PREFIXES = ("STARLINK", "ONEWEB", "IRIDIUM", "GLOBALSTAR", "ORBCOMM", "FLOCK",
                     "LEMUR", "SPACEBEE", "COSMOS", "SL-", "CZ-")
NO_PHOTO_SUFFIXES = (" DEB", " R/B")

# Many NASA "satellite" results are pictures TAKEN BY a satellite, not OF it. Drop those titles.
REJECT_PHRASES = ("imagery", "acquired", "image of", "captured", "taken by", "as seen")

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


def search_terms(name: str) -> Optional[tuple]:
    """(name to match, text to search), or None when NASA will not have a photo."""
    n = name.strip().upper()
    if n in ALIASES:
        return ALIASES[n], ALIASES[n]
    if n.startswith(NO_PHOTO_PREFIXES) or n.endswith(NO_PHOTO_SUFFIXES):
        return None
    base = re.sub(r"\(.*?\)", "", n).strip()           # drop "(EXTRA)"
    base = re.sub(r"[-_]+", " ", base).strip()          # "NOAA-19" -> "NOAA 19"
    return (base, f"{base} satellite") if base else None


def _unpack(sat: Union[str, dict]) -> tuple:
    """-> (name, norad_id or None). Accepts a name, or {name|OBJECT_NAME, tle1, ...}."""
    if not isinstance(sat, dict):
        return str(sat).strip(), None
    name = str(sat.get("name") or sat.get("OBJECT_NAME") or "").strip()
    norad = sat.get("NORAD_CAT_ID")
    tle1 = sat.get("tle1") or ""
    if not norad and tle1.startswith("1 "):
        norad = tle1[2:7].strip()                        # "1 25544U ..." -> "25544"
    return name, (str(norad) if norad else None)


def _is_relevant(name: str, item: dict) -> bool:
    data = item["data"][0]
    title = data.get("title", "").lower()
    if any(p in title for p in REJECT_PHRASES):
        return False
    tokens = [t for t in re.findall(r"[a-z0-9]+", name.lower()) if len(t) > 1]
    if not tokens:
        return False
    haystack = title + " " + " ".join(data.get("keywords", [])).lower()
    return sum(t in haystack for t in tokens) >= math.ceil(0.8 * len(tokens))


def _sample() -> dict:
    return {
        "source": "sample",
        "url": DRAWING_URL,
        "title": "Illustration of a satellite",
        "caption": "Illustration, not a photo. No photo of this satellite is available.",
        "credit": "Near Earth Explorer",
        "page": None,
        "sample_url": SAMPLE_SATELLITE_URL,
        "illustrative": True,
    }


async def _search(client: httpx.AsyncClient, params: dict) -> list:
    for attempt in range(2):                             # one retry on timeout
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
        "sample_url": SAMPLE_SATELLITE_URL,
        "illustrative": False,
    }


async def _lookup(client: httpx.AsyncClient, name: str) -> dict:
    pinned = CURATED.get(name.upper())
    if pinned:                                           # exact photo you chose
        for item in await _search(client, {"nasa_id": pinned}):
            if item.get("links"):
                return await _photo(client, item)
    terms = search_terms(name)
    if terms:                                            # unlisted/commercial ones skip the search
        match_name, query = terms
        params = {"q": query, "media_type": "image", "page_size": 10}
        for item in await _search(client, params):
            if item.get("links") and _is_relevant(match_name, item):
                return await _photo(client, item)
    return _sample()


async def get_satellite_image(sat: Union[str, dict],
                              client: Optional[httpx.AsyncClient] = None) -> dict:
    name, norad = _unpack(sat)
    extra = {"name": name, "norad_id": norad,
             "info_url": f"https://www.n2yo.com/satellite/?s={norad}" if norad else None}
    if name in _cache():
        return {**_cache()[name], **extra}

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=10, follow_redirects=True)
    try:
        result = await _lookup(client, name)
    except (httpx.HTTPError, KeyError, ValueError):
        return {**_sample(), **extra}                    # network trouble: show the drawing, do not cache
    finally:
        if own_client:
            await client.aclose()

    _cache()[name] = result
    _save_cache()
    return {**result, **extra}


async def get_satellite_images(sats: list, concurrency: int = 3) -> list:
    """Look up many satellites at once, at most `concurrency` NASA calls in flight."""
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        async def one(s: Any) -> dict:
            async with sem:
                return await get_satellite_image(s, client)
        return await asyncio.gather(*(one(s) for s in sats))


try:  # lets M1 mount it with app.include_router(router)
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/api/satellite-image")
    async def satellite_image_endpoint(name: str):
        return await get_satellite_image(name)
except ImportError:
    pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(asyncio.run(get_satellite_image(sys.argv[1])), indent=2))
    else:
        print(__doc__)
