"""Image services (M3): NASA photos for objects, plus our own asteroid drawing as a fallback.

Wiring in M1's main.py (same pattern as audio):

    from images import asteroid_router, image_router, mount_images
    app.include_router(asteroid_router)   # GET /api/asteroid-image?name=
    app.include_router(image_router)      # GET /api/image?name=&kind=   (satellites, planets)
    mount_images(app)                     # serves /static/fallbacks/*.svg and *.jpg

and where an object's detail is built:

    from images import get_asteroid_image, get_image
    image = await get_asteroid_image(neo_item)      # neo_item = the NeoWs dict, or just the name
    image = get_image("ISS (ZARYA)", "satellite")   # sync; use asyncio.to_thread in async code

Every result has `url`, `caption`, `credit`, `illustrative`. The UI must show `caption`
whenever `illustrative` is true. `sample_url` is the transparent asteroid icon for the map.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .asteroid_image import get_asteroid_image, get_asteroid_images
from .asteroid_image import router as asteroid_router
from .nasa_images import get_image
from .nasa_images import router as image_router

STATIC_DIR = Path(__file__).parent / "static"


def mount_images(app: FastAPI) -> None:
    (STATIC_DIR / "fallbacks").mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="image-static")


__all__ = [
    "asteroid_router",
    "get_asteroid_image",
    "get_asteroid_images",
    "get_image",
    "image_router",
    "mount_images",
]
