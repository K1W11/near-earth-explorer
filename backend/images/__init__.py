"""Image services (M3): NASA photos for objects, plus our own asteroid drawing as a fallback.

Wiring in M1's main.py (same pattern as audio):

    from images import asteroid_router, satellite_router, image_router, mount_images
    app.include_router(asteroid_router)    # GET /api/asteroid-image?name=
    app.include_router(satellite_router)   # GET /api/satellite-image?name=
    app.include_router(image_router)       # GET /api/image?name=&kind=   (planets)
    mount_images(app)                      # serves /static/fallbacks/*.svg and *.jpg

and where an object's detail is built:

    from images import get_asteroid_image, get_satellite_image
    image = await get_asteroid_image(neo_item)    # the NeoWs dict, or just the name
    image = await get_satellite_image(sat)        # the pipeline dict {name, tle1, tle2}, or the name

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
from .satellite_image import get_satellite_image, get_satellite_images
from .satellite_image import router as satellite_router

STATIC_DIR = Path(__file__).parent / "static"


def mount_images(app: FastAPI) -> None:
    (STATIC_DIR / "fallbacks").mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="image-static")


__all__ = [
    "asteroid_router",
    "get_asteroid_image",
    "get_asteroid_images",
    "get_image",
    "get_satellite_image",
    "get_satellite_images",
    "image_router",
    "mount_images",
    "satellite_router",
]
