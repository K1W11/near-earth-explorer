"""FastAPI wiring.  In M1's app:

    from audio.router import router as audio_router, mount_audio
    app.include_router(audio_router)
    mount_audio(app)

and in the story endpoint:

    from audio import narrate, audio_url
    return {"text": text, "audio_url": audio_url(narrate(text))}
"""
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .voice import AUDIO_DIR, AudioError, audio_url, narrate

router = APIRouter()


class NarrateRequest(BaseModel):
    text: str


@router.post("/api/narrate")
def narrate_endpoint(body: NarrateRequest):
    try:
        return {"audio_url": audio_url(narrate(body.text))}
    except AudioError as e:
        raise HTTPException(status_code=502, detail=str(e))


def mount_audio(app: FastAPI) -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
