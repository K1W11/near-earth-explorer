"""Centralized, lazy Gemini client configuration for the backend."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

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

    # GOOGLE_API_KEY is the google-genai SDK's own variable name; accept it as
    # a fallback so either convention works.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured. Set it (or GOOGLE_API_KEY) "
            "in backend/.env."
        )

    # Vertex AI express-mode keys start with "AQ." and are rejected by the
    # Gemini Developer API (API_KEY_INVALID). AI Studio keys start with "AIza".
    # Auto-detect by prefix; GEMINI_USE_VERTEX=1/0 forces either mode.
    force = os.getenv("GEMINI_USE_VERTEX", "").strip().lower()
    use_vertex = (
        force in {"1", "true", "yes"}
        if force
        else api_key.startswith("AQ.")
    )

    if use_vertex:
        # Leave api_version to the SDK's Vertex default unless set explicitly.
        explicit_version = os.getenv("GEMINI_API_VERSION")
        http_options = (
            types.HttpOptions(api_version=explicit_version) if explicit_version else None
        )
        _client = genai.Client(
            vertexai=True, api_key=api_key, http_options=http_options
        )
    else:
        api_version = os.getenv("GEMINI_API_VERSION", "v1beta")
        _client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version=api_version),
        )
    return _client
