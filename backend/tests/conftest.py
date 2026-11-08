"""Shared pytest fixtures for the Near Earth Explorer backend test suite.

The fixtures in this module provide an isolated ASGI client and deterministic
upstream/SDK responses. Individual test modules consume them according to their
responsibility: route behavior in ``test_routes.py``, Gemini orchestration in
``test_assistant.py``, ElevenLabs streaming in ``test_narration.py``, the
upstream parsers/cache in ``test_data_pipeline.py``, and TLE propagation in
``test_look_angles.py``. No fixture performs live network requests or requires
provider credentials.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import httpx
import pytest
import pytest_asyncio

# Test commands may be run from the repository root or backend/. Add the
# backend directory so imports resolve consistently with ``uvicorn main:app``.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import main


@pytest.fixture(scope="session")
def event_loop():
    """Provide one session-scoped asyncio loop for async backend test modules.

    Consumers: ``test_routes.py``, ``test_assistant.py``, and
    ``test_narration.py`` use asynchronous endpoint requests; data pipeline
    tests may also use the loop to await fetch functions directly.
    """
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest_asyncio.fixture
async def async_test_client():
    """Yield an async HTTP client connected directly to the FastAPI ASGI app.

    Consumers: ``test_routes.py``, ``test_assistant.py``, and
    ``test_narration.py`` use this fixture to call routes without binding a
    network port. ``ASGITransport`` is used instead of HTTPX's removed
    ``app=`` shortcut so the fixture works with current HTTPX releases.
    """
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def mock_nasa_payload():
    """Return a stable NeoWs feed response with a valid close-approach record.

    Consumers: ``test_data_pipeline.py`` validates feed flattening, unit
    conversion, and miss-distance sorting; ``test_routes.py`` uses the same
    structure to exercise the closest-asteroid API response.
    """
    return {
        "near_earth_objects": {
            "2026-11-07": [
                {
                    "id": "2465633",
                    "name": "(465633) 2009 JR5",
                    "estimated_diameter": {
                        "kilometers": {
                            "estimated_diameter_min": 0.18,
                            "estimated_diameter_max": 0.41,
                        }
                    },
                    "is_potentially_hazardous_asteroid": True,
                    "close_approach_data": [
                        {
                            "close_approach_date": "2026-Nov-08",
                            "close_approach_date_full": "2026-Nov-08 12:34",
                            "miss_distance": {
                                "astronomical": "0.012",
                                "kilometers": "1795000.0",
                            },
                            "relative_velocity": {
                                "kilometers_per_second": "12.5",
                                "kilometers_per_hour": "45000.0",
                            },
                        }
                    ],
                    "nasa_jpl_url": "https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr=2465633",
                }
            ]
        }
    }


@pytest.fixture
def mock_celestrak_payload():
    """Return one valid CelesTrak three-line ISS TLE block.

    Consumers: ``test_data_pipeline.py`` checks name/TLE parsing and
    ``test_look_angles.py`` uses the element set as input to SGP4 propagation.
    The lines use the canonical name, line-1, line-2 ordering returned by the
    active CelesTrak TLE text endpoint.
    """
    return (
        "ISS (ZARYA)\n"
        "1 25544U 98067A   21275.51005787  .00001446  00000-0  33231-4 0  9993\n"
        "2 25544  51.6442 208.9163 0003886  92.4401  33.3421 15.48815329302845\n"
    )


@pytest.fixture
def mock_time():
    """Patch the pipeline's wall clock with a manually advanceable value.

    Consumers: ``test_data_pipeline.py`` can set ``mock_time.return_value`` to
    an initial epoch, perform a cached fetch, then add more than 3600 seconds
    and verify that the expired dataset is fetched again.
    """
    with mock.patch("data_pipeline.time.time", return_value=1_800_000_000.0) as clock:
        yield clock


@pytest.fixture
def mock_gemini_client():
    """Patch the Gemini client with function-call then final-text responses.

    Consumers: ``test_assistant.py`` exercise the two-turn tool execution
    lifecycle. The first response requests ``get_closest_asteroid`` and carries
    candidate conversation content; the next response supplies synthesized
    answer text. The yielded mock is the patched ``main.genai.Client`` class,
    so tests can inspect its instantiated client's generation calls.
    """
    function_call = SimpleNamespace(
        name="get_closest_asteroid",
        args={"count": 1},
    )
    tool_call_response = SimpleNamespace(
        function_calls=[function_call],
        candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))],
        text=None,
    )
    final_text_response = SimpleNamespace(
        function_calls=[],
        candidates=[],
        text="The closest asteroid is 2009 JR5.",
    )

    with mock.patch("main.genai.Client") as client_class:
        client = client_class.return_value
        client.models.generate_content.side_effect = [
            tool_call_response,
            final_text_response,
        ]
        yield client_class


@pytest.fixture
def mock_elevenlabs_client():
    """Patch ElevenLabs with a deterministic iterator of MP3 byte chunks.

    Consumers: ``test_narration.py`` checks the narration route's streaming
    response content type and chunked audio body without contacting the
    ElevenLabs service. The current backend consumes
    ``client.text_to_speech.stream``; the mocked iterator yields the same kind
    of byte chunks a streaming SDK response supplies.
    """
    audio_chunks = [b"dummy", b"audio", b"bytes"]
    with mock.patch("main.ElevenLabs") as client_class:
        client = client_class.return_value
        client.text_to_speech.stream.return_value = iter(audio_chunks)
        yield client_class