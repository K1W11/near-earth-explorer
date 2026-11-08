"""Core FastAPI application for Near Earth Explorer at UB Hacking.

Architectural responsibilities:
* Expose the REST gateway consumed by the browser map for NASA asteroid data,
  CelesTrak active satellite TLEs, and observer-centered satellite look angles.
* Orchestrate Gemini 2.5 Flash structured function calls by connecting model
  requests to the shared data pipeline and SGP4 look-angle calculation engine.
* Serve cached ElevenLabs MP3 narration (see ``audio/``) to the map UI.

The route layer depends on ``data_pipeline.py`` for cached external data and
``look_angles.py`` for TLE propagation and local horizon calculations. Copy
``.env.example`` to ``.env`` to configure API credentials and server settings.
Run with ``uvicorn main:app --app-dir backend`` or execute this module directly.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from google.genai import types
from httpx import HTTPError
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from data_pipeline import fetch_active_satellites, fetch_asteroids
from urllib.parse import quote

from audio import AudioError, narrate
from gemini_client import GeminiConfigurationError, get_gemini_client
from story import get_story
from look_angles import calculate_altitude_km, calculate_look_angles
from satellite_messages import satellite_overview, format_satellite_message

logger = logging.getLogger("near_earth_explorer")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
"""Model used to understand astronomy questions and request structured tools."""

app = FastAPI(
    title="Near Earth Explorer Backend",
    description=(
        "FastAPI gateway for NASA NeoWs asteroid data, CelesTrak satellite "
        "tracking, SGP4 observer look angles, Gemini assistant tools, and "
        "ElevenLabs audio narration."
    ),
    version="1.0.0",
)

# The frontend is developed independently and can run on different localhost
# ports. The wildcard origin is intentional for the hackathon development API;
# credential support is enabled as requested for cross-origin frontend calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Lets browser JS read the narration transcript sent with the audio.
    expose_headers=["X-Narration-Text"],
)


class QueryRequest(BaseModel):
    """Request body for assistant queries and observer-location context.

    Schema:
        query: Natural-language question from the frontend.
        user_lat: Observer latitude in degrees; defaults to UB Davis Hall.
        user_lon: Observer longitude in degrees; defaults to UB Davis Hall.
    """

    query: str = Field(min_length=1, max_length=4000)
    user_lat: float = Field(default=43.0008, ge=-90.0, le=90.0)
    user_lon: float = Field(default=-78.7889, ge=-180.0, le=180.0)


class NarrationRequest(BaseModel):
    """Request body describing the selected map target for narration.

    Schema:
        object_name: Human-readable target name displayed by the map.
        object_type: Target kind, restricted to ``satellite`` or ``asteroid``.
    """

    object_name: str = Field(min_length=1, max_length=200)
    object_type: Literal["satellite", "asteroid"]
    category: Literal["overview", "orbital_position", "tracking"] = "overview"


class SatelliteRecord(BaseModel):
    """Normalized active satellite record returned to the frontend."""

    name: str
    tle1: str
    tle2: str
    altitude_km: float | None


class ActiveSatellitesResponse(BaseModel):
    """Active satellite records and the number returned."""

    count: int
    satellites: list[SatelliteRecord]


class SatelliteOverview(BaseModel):
    """Structured TLE-derived satellite facts for the frontend."""

    name: str
    norad_catalog_number: str
    classification: str
    international_designator: str
    elements_epoch: str
    altitude_km: float | None
    orbit_class: str
    orbit_description: str
    orbital_period_minutes: float
    inclination_degrees: float
    eccentricity: float
    right_ascension_ascending_node_degrees: float
    argument_of_perigee_degrees: float
    mean_anomaly_degrees: float
    mean_motion_revolutions_per_day: float
    revolutions_at_epoch: str
    tle1: str
    tle2: str


def _tool_declarations() -> list[types.Tool]:
    """Declare the read-only application functions available to Gemini.

    The declaration schemas constrain arguments before the backend executes
    either a nearest-asteroid lookup or an observer-specific satellite search.
    """
    asteroid_declaration = types.FunctionDeclaration(
        name="get_closest_asteroid",
        description=(
            "Fetch the nearest asteroid to Earth by miss distance from the "
            "upcoming seven-day NASA NeoWs feed."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "count": types.Schema(
                    type=types.Type.INTEGER,
                    description="Optional number of closest asteroid records (1 to 5).",
                )
            },
        ),
    )
    look_angles_declaration = types.FunctionDeclaration(
        name="get_observer_look_angles",
        description=(
            "Find a satellite by name in the active TLE catalog and calculate "
            "its azimuth, elevation, range, and cardinal direction."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "satellite_name": types.Schema(
                    type=types.Type.STRING,
                    description="Satellite name or distinctive substring, for example ISS.",
                )
            },
            required=["satellite_name"],
        ),
    )
    return [
        types.Tool(
            function_declarations=[
                asteroid_declaration,
                look_angles_declaration,
            ]
        )
    ]


async def _execute_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    request: QueryRequest,
) -> dict[str, Any]:
    """Run one Gemini tool request using the shared backend services.

    Args:
        tool_name: Declared function name returned by Gemini.
        arguments: JSON-like arguments supplied by the model.
        request: Original query, including observer coordinates.

    Returns:
        JSON-serializable data from NeoWs or the SGP4 look-angle engine. Invalid
        tool arguments return a structured ``error`` result for model context.
    """
    if tool_name == "get_closest_asteroid":
        count = arguments.get("count", 1)
        if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 5:
            return {"error": "count must be an integer between 1 and 5"}
        try:
            asteroids = await fetch_asteroids(os.getenv("NASA_API_KEY", "DEMO_KEY"))
        except HTTPError as error:
            logger.warning("NASA NeoWs request failed during Gemini tool call: %s", error)
            raise HTTPException(
                status_code=502,
                detail="NASA NeoWs is temporarily unavailable.",
            ) from error
        return {
            "closest_asteroid": asteroids[0] if asteroids else None,
            "asteroids": asteroids[:count],
            "total_7_day_count": len(asteroids),
        }

    if tool_name == "get_observer_look_angles":
        satellite_name = arguments.get("satellite_name")
        if not isinstance(satellite_name, str) or not satellite_name.strip():
            return {"error": "satellite_name must be a non-empty string"}

        try:
            satellites = await fetch_active_satellites()
        except HTTPError as error:
            logger.warning("CelesTrak request failed during Gemini tool call: %s", error)
            raise HTTPException(
                status_code=502,
                detail="CelesTrak is temporarily unavailable.",
            ) from error

        normalized_name = satellite_name.casefold().strip()
        match = next(
            (
                satellite
                for satellite in satellites
                if normalized_name in satellite.get("name", "").casefold()
            ),
            None,
        )
        if match is None:
            return {"error": f"No active satellite matched '{satellite_name}'"}

        try:
            return calculate_look_angles(
                tle_line1=match["tle1"],
                tle_line2=match["tle2"],
                observer_lat=request.user_lat,
                observer_lon=request.user_lon,
                satellite_name=match["name"],
            )
        except (KeyError, ValueError) as error:
            logger.warning("Could not calculate look angles for %s: %s", satellite_name, error)
            return {
                "error": "The selected satellite's TLE could not be propagated.",
                "satellite_name": match.get("name", satellite_name),
            }

    # Tool names are limited to the declarations above; this guard ensures an
    # unexpected model response never dispatches arbitrary backend behavior.
    return {"error": f"Unsupported tool: {tool_name}"}


async def _generate_content(
    client: Any,
    contents: Any,
    tools: list[types.Tool],
) -> Any:
    """Call the synchronous Gemini SDK away from FastAPI's event-loop thread.

    Args:
        client: Authenticated Gen AI client for the configured API key.
        contents: User prompt or the conversation history for tool execution.
        tools: Structured function declarations available to the model.

    Returns:
        Gemini GenerateContentResponse, including text or requested function
        calls. Provider errors are surfaced to the calling route.
    """
    config = types.GenerateContentConfig(
        tools=tools,
        temperature=0.3,
        system_instruction=(
            "You are the Near Earth Explorer astronomy assistant. Use tools for "
            "current asteroid and satellite facts. Do not invent tool results; "
            "explain measured distances and sky directions in clear language."
        ),
    )
    return await asyncio.to_thread(
        client.models.generate_content,
        model=GEMINI_MODEL,
        contents=contents,
        config=config,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight liveness response without calling external APIs.

    Response schema:
        ``status``: Always ``ok`` while the FastAPI process is serving requests.
        ``service``: Stable service name used by local health checks.
    """
    return {"status": "ok", "service": "Near Earth Explorer Backend"}


@app.get("/api/asteroids/closest")
async def closest_asteroid() -> dict[str, Any]:
    """Return the closest upcoming NeoWs asteroid and the seven-day total.

    The data pipeline normalizes and sorts the seven-day NASA feed by ascending
    miss distance. The response schema contains ``closest_asteroid`` (the
    first record, or null when the window is empty) and ``total_7_day_count``.
    """
    try:
        asteroids = await fetch_asteroids(os.getenv("NASA_API_KEY", "DEMO_KEY"))
    except HTTPError as error:
        logger.warning("NASA NeoWs request failed: %s", error)
        raise HTTPException(
            status_code=502,
            detail="NASA NeoWs is temporarily unavailable.",
        ) from error
    return {
        "closest_asteroid": asteroids[0] if asteroids else None,
        "total_7_day_count": len(asteroids),
    }


@app.get("/api/satellites/active")
async def active_satellites(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum satellites to return."),
) -> ActiveSatellitesResponse:
    """Return at most ``limit`` active CelesTrak satellites and their TLEs.

    Query schema:
        ``limit``: Optional integer from 1 through 500, defaulting to 50.

    Response schema includes the returned ``satellites`` list and its ``count``.
    Each record contains a satellite name, NORAD ID, and both TLE lines used by
    the observer look-angle endpoint.
    """
    try:
        satellites = await fetch_active_satellites()
    except HTTPError as error:
        logger.warning("CelesTrak request failed: %s", error)
        raise HTTPException(
            status_code=502,
            detail="CelesTrak is temporarily unavailable.",
        ) from error
    selected = []
    for satellite in satellites[:limit]:
        try:
            altitude_km = calculate_altitude_km(satellite["tle1"], satellite["tle2"])
        except ValueError as error:
            logger.warning("Satellite %s has unavailable altitude: %s", satellite["name"], error)
            selected.append({**satellite, "altitude_km": None})
            continue
        selected.append({**satellite, "altitude_km": round(altitude_km, 1)})
    return ActiveSatellitesResponse(count=len(selected), satellites=selected)


@app.get("/api/satellites/overview", response_model=SatelliteOverview)
async def satellite_overview_route(
        name: str = Query(min_length=1, max_length=200),
) -> SatelliteOverview:
        """Return structured, backend-derived facts for one active satellite."""
        satellites = await fetch_active_satellites()
        normalized_name = name.strip().casefold()
        for satellite in satellites:
            if satellite["name"].strip().casefold() == normalized_name:
                try:
                    return SatelliteOverview(**satellite_overview(satellite))
                except (KeyError, ValueError) as error:
                    raise HTTPException(
                        status_code=422,
                        detail="The selected satellite has invalid orbital data.",
                    ) from error
        raise HTTPException(status_code=404, detail=f"No active satellite matched '{name}'")


@app.post("/api/observer/look-angles")
async def observer_look_angles(
    request: QueryRequest,
    tle1: str = Query(..., min_length=69, max_length=80, description="Satellite TLE line 1."),
    tle2: str = Query(..., min_length=69, max_length=80, description="Satellite TLE line 2."),
) -> dict[str, Any]:
    """Calculate satellite sky coordinates for the observer in the request body.

    Request schema:
        JSON body: ``QueryRequest`` with query text and optional user coordinates.
        Query parameters: ``tle1`` and ``tle2`` containing one complete TLE set.

    Response schema includes ``azimuth_deg``, ``elevation_deg``, ``range_km``,
    ``compass_direction``, visibility, observer coordinates, and calculation
    time from ``calculate_look_angles``. Invalid TLEs or propagation failures
    are returned as HTTP 422 with an explicit validation detail.
    """
    try:
        return calculate_look_angles(
            tle_line1=tle1,
            tle_line2=tle2,
            observer_lat=request.user_lat,
            observer_lon=request.user_lon,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/assistant/query")
async def assistant_query(request: QueryRequest) -> dict[str, Any]:
    """Answer a question with Gemini 2.5 Flash and at most one tool round trip.

    Request JSON schema:
        ``query``: User's natural-language astronomy question.
        ``user_lat`` / ``user_lon``: Observer location for look-angle tools.

    Response JSON schema:
        ``query``: Original user question.
        ``executed_tools``: Ordered records with each called tool's name,
            arguments, and execution result for the judging/UI console.
        ``response``: Gemini's synthesized natural-language answer.

    Turn one sends the prompt and function declarations. If Gemini asks for
    tools, this route executes each declared function, sends function results
    back in turn two, and returns the synthesized answer.
    """
    try:
        client = get_gemini_client()
    except GeminiConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not configured.",
        ) from error

    tools = _tool_declarations()
    prompt = (
        f"Observer location: latitude {request.user_lat}, longitude "
        f"{request.user_lon}. User question: {request.query}"
    )
    executed_tools: list[dict[str, Any]] = []

    try:
        first_response = await _generate_content(client, prompt, tools)
        function_calls = first_response.function_calls or []
        if not function_calls:
            answer = first_response.text
            if not answer:
                raise HTTPException(
                    status_code=502,
                    detail="Gemini returned no text answer.",
                )
            return {
                "query": request.query,
                "executed_tools": executed_tools,
                "response": answer,
            }

        candidate = (
            first_response.candidates[0]
            if first_response.candidates
            else None
        )
        if candidate is None or candidate.content is None:
            raise HTTPException(
                status_code=502,
                detail="Gemini returned tool calls without conversation content.",
            )

        function_response_parts: list[types.Part] = []
        for function_call in function_calls:
            tool_name = function_call.name or ""
            arguments = dict(function_call.args or {})
            result = await _execute_tool_call(tool_name, arguments, request)
            executed_tools.append(
                {"name": tool_name, "args": arguments, "result": result}
            )
            function_response_parts.append(
                types.Part.from_function_response(
                    name=tool_name,
                    response=result,
                )
            )

        # Preserve Gemini's function-call candidate as conversation history and
        # provide each matching result as a user-role function response.
        second_contents = [
            prompt,
            candidate.content,
            types.Content(role="user", parts=function_response_parts),
        ]
        final_response = await _generate_content(client, second_contents, tools)
        if final_response.function_calls:
            raise HTTPException(
                status_code=502,
                detail="Gemini requested more than one tool-call turn.",
            )
        answer = final_response.text
        if not answer:
            raise HTTPException(
                status_code=502,
                detail="Gemini returned no synthesized answer after tool execution.",
            )
        return {
            "query": request.query,
            "executed_tools": executed_tools,
            "response": answer,
        }
    except HTTPException:
        raise
    except Exception as error:
        # Do not log provider exception text: SDK errors may include request
        # details. Keep diagnostics to the exception type, never its contents.
        logger.error(
            "Gemini assistant request failed (%s).",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Gemini is temporarily unavailable; please try again.",
        ) from error


@app.post("/api/audio/narrate")
async def narrate_target(request: NarrationRequest) -> FileResponse:
    """Return an ElevenLabs narration of a Gemini-written story for one object.

    Request JSON schema:
        ``object_name``: Map target name.
        ``object_type``: ``satellite`` or ``asteroid``.

    Response is an ``audio/mpeg`` file. The spoken text is also sent in the
    ``X-Narration-Text`` header, percent-encoded (decode with
    ``decodeURIComponent``). The story is built from the object's real data by
    ``story.get_story`` and cached, then voiced by ``audio.narrate``, which is
    cached too, so repeat requests cost no Gemini or ElevenLabs usage and work
    offline. If facts or Gemini are unavailable a generic sentence is narrated
    instead. Provider failures return a JSON 502 *before* any audio is sent.
    """
    if request.object_type == "satellite":
        satellites = await fetch_active_satellites()
        normalized_name = request.object_name.strip().casefold()
        satellite = next(
            (
                item for item in satellites
                if item["name"].strip().casefold() == normalized_name
            ),
            None,
        )
        if satellite is None:
            raise HTTPException(
                status_code=404,
                detail=f"No active satellite matched '{request.object_name}'",
            )
        try:
            narration = format_satellite_message(
                satellite_overview(satellite),
                request.category,
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(
                status_code=422,
                detail="The selected satellite has invalid orbital data.",
            ) from error
    else:
        narration = await get_story(request.object_name, request.object_type)
    try:
        # narrate() blocks on the ElevenLabs HTTP call, so keep it off the loop.
        path = await run_in_threadpool(narrate, narration)
    except AudioError as error:
        logger.error("Narration failed for %s: %s", request.object_name, error)
        raise HTTPException(status_code=502, detail=str(error)) from error
    return FileResponse(
        path,
        media_type="audio/mpeg",
        headers={"X-Narration-Text": quote(narration)},
    )


if __name__ == "__main__":
    """Start the application directly using configured host and port values."""
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
