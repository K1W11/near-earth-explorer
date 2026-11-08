"""NASA image service for Near Earth Explorer (M3).

Usage from code:
    from nasa_images import get_image
    get_image("ISS (ZARYA)", "satellite")
    -> {"url", "title", "credit", "page", "source": "nasa" | "fallback"}

Command line:
    python nasa_images.py "Hubble Space Telescope" satellite
    python nasa_images.py --fetch-fallbacks      # run once, before the demo

No API key needed. Call this from the backend only (never the browser).
"""
import json
import math
import pathlib
import re
import sys

import requests

SEARCH_URL = "https://images-api.nasa.gov/search"
HERE = pathlib.Path(__file__).parent
CACHE_FILE = HERE / "image_cache.json"
FALLBACK_DIR = HERE / "static" / "fallbacks"
FALLBACK_URL_PREFIX = "/static/fallbacks"

# CelesTrak names are not what people write. Map the ones you demo.
ALIASES = {
    "ISS (ZARYA)": "International Space Station",
    "ISS": "International Space Station",
    "CSS (TIANHE)": "Tiangong space station",
    "HST": "Hubble Space Telescope",
}

STOPWORDS = {"the", "of", "a", "an", "and", "space"}  # "space" is too generic to prove relevance

# NeoWs names: "(2024 XY5)" = unnamed, provisional designation -> NASA has no photo of it.
#              "433 Eros (A898 PA)" / "99942 Apophis (2004 MN4)" = named -> may have photos.
PROVISIONAL = re.compile(r"^\(?\s*\d{4}\s+[A-Z]{1,2}\d*\s*\)?$")


def _asteroid_name(name: str):
    """Searchable name for a NeoWs asteroid, or None if it is an unnamed rock."""
    name = name.strip()
    if PROVISIONAL.match(name):
        return None
    base = re.sub(r"\(.*?\)", "", name).strip()   # "433 Eros (A898 PA)" -> "433 Eros"
    base = re.sub(r"^\d+\s+", "", base)           # -> "Eros"
    return base or None


# What to search for when we need a generic picture for each kind.
GENERIC_QUERIES = {                       # asteroids and satellites use our own drawings (see _fallback)
    "planet": "planet",
}


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def _clean_query(name: str) -> str:
    if name in ALIASES:
        return ALIASES[name]
    name = re.sub(r"\(.*?\)", "", name)          # "NAME (EXTRA)" -> "NAME"
    name = re.sub(r"-\d+$", "", name.strip())     # "STARLINK-1234" -> "STARLINK"
    return name.strip()


def _search(query: str, page_size: int = 10) -> list:
    params = {"q": query, "media_type": "image", "page_size": page_size}
    for attempt in range(2):                      # one retry on timeout
        try:
            r = requests.get(SEARCH_URL, params=params, timeout=10)
            r.raise_for_status()
            return r.json()["collection"]["items"]
        except requests.Timeout:
            if attempt == 1:
                raise
    return []


def _is_relevant(query: str, item: dict) -> bool:
    tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if t not in STOPWORDS]
    if not tokens:
        return False
    data = item["data"][0]
    haystack = (data.get("title", "") + " " + " ".join(data.get("keywords", []))).lower()
    hits = sum(1 for t in tokens if t in haystack)
    return hits >= math.ceil(0.6 * len(tokens))


def _best_url(thumb_url: str) -> str:
    """NASA serves ~thumb, ~small, ~medium, ~large, ~orig. Use medium if it exists."""
    if "~thumb" not in thumb_url:
        return thumb_url
    medium = thumb_url.replace("~thumb", "~medium")
    try:
        if requests.head(medium, timeout=5, allow_redirects=True).ok:
            return medium
    except requests.RequestException:
        pass
    return thumb_url


def _result(item: dict) -> dict:
    data = item["data"][0]
    return {
        "url": _best_url(item["links"][0]["href"]),
        "title": data.get("title", ""),
        "credit": "NASA",
        "page": f"https://images.nasa.gov/details/{data['nasa_id']}",
        "source": "nasa",
        "illustrative": False,
        "caption": f"{data.get('title', '')} (NASA)",
    }


def _fallback(kind: str) -> dict:
    # UI: always show `caption` when illustrative is true, so nobody mistakes it for the real object.
    if kind == "asteroid":
        # Our own drawing, the same asteroid the Earth view uses. static/fallbacks/asteroid.svg
        # (dark space backdrop, for the detail page); sample-asteroid.svg is the transparent map icon.
        return {
            "url": f"{FALLBACK_URL_PREFIX}/asteroid.svg",
            "sample_url": f"{FALLBACK_URL_PREFIX}/sample-asteroid.svg",
            "title": "Illustration of an asteroid",
            "credit": "Near Earth Explorer",
            "page": None,
            "source": "illustration",
            "illustrative": True,
            "caption": "Illustration, not a photo. No photo of this asteroid exists.",
        }
    if kind == "satellite":
        # Our own drawing (see satellite_image.py, the full satellite service).
        return {
            "url": f"{FALLBACK_URL_PREFIX}/satellite.svg",
            "sample_url": f"{FALLBACK_URL_PREFIX}/sample-satellite.svg",
            "title": "Illustration of a satellite",
            "credit": "Near Earth Explorer",
            "page": None,
            "source": "illustration",
            "illustrative": True,
            "caption": "Illustration, not a photo. No photo of this satellite is available.",
        }
    return {
        "url": f"{FALLBACK_URL_PREFIX}/{kind}.jpg",
        "title": f"Generic {kind}",
        "credit": "NASA",
        "page": "https://images.nasa.gov",
        "source": "fallback",
        "illustrative": True,
        "caption": f"Illustrative image of a typical {kind} (NASA). No photo of this exact object exists.",
    }


def get_image(name: str, kind: str = "satellite") -> dict:
    """Never raises. Always returns something the UI can show."""
    cache = _load_cache()
    key = f"{kind}:{name}"
    if key in cache:
        return cache[key]

    result = None
    try:
        if kind == "asteroid":
            match_name = _asteroid_name(name)     # None -> unnamed rock, skip the search
            search_text = f"{match_name} asteroid" if match_name else None
        else:
            match_name = search_text = _clean_query(name)
        if match_name:
            for item in _search(search_text):
                if item.get("links") and _is_relevant(match_name, item):
                    result = _result(item)
                    break
    except (requests.RequestException, KeyError, ValueError):
        return _fallback(kind)                    # network trouble: do not cache the miss

    result = result or _fallback(kind)
    cache[key] = result
    _save_cache(cache)
    return result


def fetch_fallbacks() -> None:
    """Download one generic picture per kind into static/fallbacks/. Run once."""
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    for kind, query in GENERIC_QUERIES.items():
        items = [i for i in _search(query, page_size=5) if i.get("links")]
        if not items:
            print(f"no image found for {kind}")
            continue
        info = _result(items[0])
        (FALLBACK_DIR / f"{kind}.jpg").write_bytes(requests.get(info["url"], timeout=20).content)
        print(f"saved {kind}.jpg  <- {info['title']}  ({info['page']})")


try:  # optional: lets M1 mount this with app.include_router(router)
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/api/image")
    def image_endpoint(name: str, kind: str = "satellite"):
        return get_image(name, kind)
except ImportError:
    pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fetch-fallbacks":
        fetch_fallbacks()
    elif len(sys.argv) > 1:
        print(json.dumps(get_image(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "satellite"), indent=2))
    else:
        print(__doc__)
