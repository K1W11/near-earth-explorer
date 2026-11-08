"""ElevenLabs narration with a content-addressed file cache.

narrate(text) -> Path to an mp3. Same (voice, model, text) never costs credits twice.
"""
from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel"; override with ELEVENLABS_VOICE_ID in .env
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
APPLY_TEXT_NORMALIZATION = "on"
OUTPUT_FORMAT = "mp3_44100_128"
MAX_CHARS = 1200  # a 60-80 word story is ~450 chars; this guards against runaway credit spend

AUDIO_DIR = Path(os.getenv("AUDIO_CACHE_DIR", Path(__file__).resolve().parent.parent / "audio_cache"))

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


class AudioError(RuntimeError):
    """Raised when narration cannot be produced (missing key, bad request, API failure)."""


def _settings() -> tuple[str, str, str]:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise AudioError("ELEVENLABS_API_KEY is not set")
    return (
        key,
        os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID),
        os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID),
    )


def cache_path(text: str, voice_id: str, model_id: str) -> Path:
    digest = hashlib.sha256(f"{voice_id}|{model_id}|{text}".encode()).hexdigest()[:16]
    return AUDIO_DIR / f"{digest}.mp3"


def narrate(text: str) -> Path:
    """Return the mp3 for `text`, generating it via ElevenLabs on a cache miss."""
    text = " ".join(text.split())
    if not text:
        raise AudioError("Nothing to narrate: text is empty")
    if len(text) > MAX_CHARS:
        raise AudioError(f"Text too long ({len(text)} > {MAX_CHARS} chars)")

    voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
    model_id = os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID)
    path = cache_path(text, voice_id, model_id)
    if path.exists():  # cache hits must work with no API key / no internet (offline demo)
        return path
    api_key = _settings()[0]

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    with _locks_guard:
        lock = _locks.setdefault(path.name, threading.Lock())
    with lock:  # two simultaneous clicks on one object bill only once
        if path.exists():
            return path
        try:
            r = httpx.post(
                f"{API_URL}/{voice_id}",
                params={"output_format": OUTPUT_FORMAT},
                headers={"xi-api-key": api_key},
                json={
                    "text": text,
                    "model_id": model_id,
                    "apply_text_normalization": APPLY_TEXT_NORMALIZATION,
                },
                timeout=60,
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise AudioError(f"ElevenLabs returned {e.response.status_code}: {e.response.text[:200]}") from e
        except httpx.HTTPError as e:
            raise AudioError(f"Could not reach ElevenLabs: {e}") from e

        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(r.content)
        tmp.replace(path)  # atomic: never serve a half-written file
    return path


def audio_url(path: Path) -> str:
    return f"/audio/{path.name}"
