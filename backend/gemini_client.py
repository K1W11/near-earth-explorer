"""Centralized, lazy Gemini client configuration for the backend."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

_ENV_FILE = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=_ENV_FILE)


class GeminiConfigurationError(RuntimeError):
    """Raised when a Gemini request is attempted without an API key."""


_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """Return the process-wide Gemini client, creating it on first use.

    Loading credentials relative to this module keeps configuration stable
    whether Uvicorn is launched from the repository root or ``backend/``.
    Lazy initialization lets non-Gemini routes and health checks run without
    credentials, while ensuring only one SDK client is created per process.
    """
    global _client

    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured. Set it in backend/.env."
        )

    _client = genai.Client(api_key=api_key)
    return _client
