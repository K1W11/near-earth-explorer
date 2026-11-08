"""Tests for the Gemini 2.5 Flash assistant endpoint and tool orchestration.

The suite exercises ``POST /api/assistant/query`` at its HTTP boundary and
directly validates the allow-listed tool dispatcher. It covers plain single-
turn answers, the two-turn Gemini function-calling flow, request validation,
and explicit handling of absent credentials or provider failures.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock
from unittest.mock import AsyncMock

import httpx
import pytest

from main import QueryRequest, _execute_tool_call


@pytest.mark.asyncio
async def test_assistant_query_missing_api_key(
    async_test_client: httpx.AsyncClient,
) -> None:
    """Return HTTP 503 when Gemini credentials are not configured."""
    with (
        mock.patch("main.os.getenv", return_value=None),
        mock.patch("main.genai.Client") as gemini_client,
    ):
        response = await async_test_client.post(
            "/api/assistant/query",
            json={"query": "Hello"},
        )

    assert response.status_code == 503
    assert "GEMINI_API_KEY is not configured" in response.json()["detail"]
    gemini_client.assert_not_called()


@pytest.mark.asyncio
async def test_assistant_query_single_turn_no_tools(
    async_test_client: httpx.AsyncClient,
) -> None:
    """Return Gemini's plain text directly when it requests no application tool."""
    gemini_response = SimpleNamespace(
        function_calls=None,
        text="The Moon is Earth's only natural satellite.",
    )
    with (
        mock.patch("main.os.getenv", return_value="fake_key"),
        mock.patch("main.genai.Client") as gemini_client,
        mock.patch(
            "main._generate_content",
            new_callable=AsyncMock,
            return_value=gemini_response,
        ) as generate_content,
    ):
        response = await async_test_client.post(
            "/api/assistant/query",
            json={
                "query": "What is the Moon?",
                "user_lat": 43.0008,
                "user_lon": -78.7889,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["executed_tools"] == []
    assert payload["response"] == "The Moon is Earth's only natural satellite."
    gemini_client.assert_called_once_with(api_key="fake_key")
    generate_content.assert_awaited_once()


@pytest.mark.asyncio
async def test_assistant_query_two_turn_tool_execution(
    async_test_client: httpx.AsyncClient,
) -> None:
    """Execute a Gemini satellite tool call and return the synthesized answer."""
    function_call = SimpleNamespace(
        name="get_observer_look_angles",
        args={"satellite_name": "ISS"},
    )
    first_response = SimpleNamespace(
        function_calls=[function_call],
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(role="model", parts=[]),
            )
        ],
        text=None,
    )
    final_answer = "The ISS is currently located at SW (225°) at 40° elevation."
    second_response = SimpleNamespace(
        function_calls=None,
        text=final_answer,
    )
    look_angles = {
        "azimuth": 225.0,
        "elevation": 40.0,
        "cardinal_direction": "SW",
        "formatted": "SW (225°) at 40° elevation",
    }

    with (
        mock.patch("main.os.getenv", return_value="fake_key"),
        mock.patch("main.genai.Client") as gemini_client,
        mock.patch(
            "main.fetch_active_satellites",
            new_callable=AsyncMock,
            return_value=[
                {
                    "name": "ISS (ZARYA)",
                    "tle1": "1 25544U...",
                    "tle2": "2 25544U...",
                }
            ],
        ) as fetch_satellites,
        mock.patch(
            "main.calculate_look_angles",
            return_value=look_angles,
        ) as calculate_angles,
        mock.patch(
            "main._generate_content",
            new_callable=AsyncMock,
            side_effect=[first_response, second_response],
        ) as generate_content,
    ):
        response = await async_test_client.post(
            "/api/assistant/query",
            json={"query": "Where is ISS?"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "Where is ISS?"
    assert len(payload["executed_tools"]) == 1
    assert payload["executed_tools"][0]["name"] == "get_observer_look_angles"
    assert payload["executed_tools"][0]["args"] == {"satellite_name": "ISS"}
    assert payload["executed_tools"][0]["result"] == look_angles
    assert payload["response"] == final_answer
    gemini_client.assert_called_once_with(api_key="fake_key")
    assert generate_content.await_count == 2
    fetch_satellites.assert_awaited_once()
    calculate_angles.assert_called_once_with(
        tle_line1="1 25544U...",
        tle_line2="2 25544U...",
        observer_lat=43.0008,
        observer_lon=-78.7889,
        satellite_name="ISS (ZARYA)",
    )


@pytest.mark.asyncio
async def test_execute_tool_call_validation_errors() -> None:
    """Reject invalid asteroid count and empty satellite name without fetching."""
    request = QueryRequest(query="Validate tool inputs")

    asteroid_result = await _execute_tool_call(
        "get_closest_asteroid",
        {"count": 99},
        request,
    )
    satellite_result = await _execute_tool_call(
        "get_observer_look_angles",
        {"satellite_name": ""},
        request,
    )

    assert asteroid_result == {
        "error": "count must be an integer between 1 and 5"
    }
    assert satellite_result == {
        "error": "satellite_name must be a non-empty string"
    }


@pytest.mark.asyncio
async def test_assistant_query_provider_exception_returns_502(
    async_test_client: httpx.AsyncClient,
) -> None:
    """Translate a Gemini SDK failure into an explicit HTTP 502 response."""
    with (
        mock.patch("main.os.getenv", return_value="fake_key"),
        mock.patch("main.genai.Client"),
        mock.patch(
            "main._generate_content",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Google GenAI SDK Network Error"),
        ),
    ):
        response = await async_test_client.post(
            "/api/assistant/query",
            json={"query": "Crash test"},
        )

    assert response.status_code == 502
    assert "Gemini is temporarily unavailable" in response.json()["detail"]