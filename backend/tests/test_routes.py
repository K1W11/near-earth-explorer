"""HTTP-level tests for the Near Earth Explorer FastAPI routes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock

import httpx
import pytest

import data_pipeline
def _parsed_asteroid_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn the shared NeoWs fixture into the route's normalized payload shape."""
    return data_pipeline._parse_asteroid_feed(payload)


def _satellite_records(payload: str, count: int) -> list[dict[str, str]]:
    """Expand the shared CelesTrak TLE fixture into distinct route records."""
    parsed = data_pipeline._parse_active_satellites(payload)
    assert parsed
    template = parsed[0]
    return [
        {
            "name": f"{template['name']} {index + 1}",
            "tle1": template["tle1"],
            "tle2": template["tle2"],
        }
        for index in range(count)
    ]


@pytest.mark.asyncio
async def test_health_check_endpoint(async_test_client: httpx.AsyncClient) -> None:
    """Verify the health route exposes its stable status and service identity."""
    response = await async_test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Near Earth Explorer Backend",
    }


@pytest.mark.asyncio
async def test_get_closest_asteroid_success(
    async_test_client: httpx.AsyncClient,
    mock_nasa_payload: dict[str, Any],
) -> None:
    """Return the nearest record and total count from normalized NEO data."""
    asteroids = _parsed_asteroid_records(mock_nasa_payload)
    farther_asteroid = deepcopy(asteroids[0])
    farther_asteroid["id"] = "9999999"
    farther_asteroid["name"] = "Farther test asteroid"
    farther_asteroid["miss_distance_km"] += 1_000_000.0
    expected_asteroids = [asteroids[0], farther_asteroid]

    with mock.patch(
        "main.fetch_asteroids",
        new_callable=AsyncMock,
        return_value=expected_asteroids,
    ) as fetch_asteroids:
        response = await async_test_client.get("/api/asteroids/closest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["closest_asteroid"] == expected_asteroids[0]
    assert payload["total_7_day_count"] == len(expected_asteroids)
    fetch_asteroids.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_closest_asteroid_upstream_error(
    async_test_client: httpx.AsyncClient,
) -> None:
    """Translate a NASA HTTP failure into the route's 502 gateway response."""
    request = httpx.Request("GET", "https://api.nasa.gov/neo/rest/v1/feed")
    upstream_response = httpx.Response(
        status_code=500,
        request=request,
        text="NASA is unavailable",
    )
    upstream_error = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=request,
        response=upstream_response,
    )

    with mock.patch(
        "main.fetch_asteroids",
        new_callable=AsyncMock,
        side_effect=upstream_error,
    ):
        response = await async_test_client.get("/api/asteroids/closest")

    assert response.status_code == 502
    assert "NASA NeoWs is temporarily unavailable." in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_active_satellites_with_limit(
    async_test_client: httpx.AsyncClient,
    mock_celestrak_payload: str,
) -> None:
    """Return no more satellite TLE records than the requested route limit."""
    satellites = _satellite_records(mock_celestrak_payload, count=10)
    altitude_km = 389.2
    expected_satellites = [
        {**satellite, "altitude_km": altitude_km}
        for satellite in satellites[:3]
    ]
    with (
        mock.patch(
            "main.fetch_active_satellites",
            new_callable=AsyncMock,
            return_value=satellites,
        ) as fetch_satellites,
        mock.patch("main.calculate_altitude_km", return_value=altitude_km),
    ):
        response = await async_test_client.get(
            "/api/satellites/active",
            params={"limit": 3},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 3
    assert len(payload["satellites"]) == 3
    assert payload["satellites"] == expected_satellites
    fetch_satellites.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_active_satellites_invalid_limit(
    async_test_client: httpx.AsyncClient,
) -> None:
    """Reject a satellite limit above the endpoint's maximum of 500."""
    response = await async_test_client.get(
        "/api/satellites/active",
        params={"limit": 1000},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_observer_look_angles_success(
    async_test_client: httpx.AsyncClient,
    mock_celestrak_payload: str,
) -> None:
    """Accept valid query-parameter TLEs and return the documented angle fields."""
    satellite_name, tle1, tle2 = mock_celestrak_payload.strip().splitlines()
    assert satellite_name == "ISS (ZARYA)"
    expected_angles = {
        "azimuth": 322.47,
        "elevation": -40.47,
        "range_km": 8916.48,
        "cardinal_direction": "NW",
        "visible": False,
    }
    request_body = {
        "query": "look angles",
        "user_lat": 43.0008,
        "user_lon": -78.7889,
    }

    with mock.patch(
        "main.calculate_look_angles",
        return_value=expected_angles,
    ) as calculate_angles:
        response = await async_test_client.post(
            "/api/observer/look-angles",
            params={"tle1": tle1, "tle2": tle2},
            json=request_body,
        )

    assert response.status_code == 200
    payload = response.json()
    assert {
        "azimuth",
        "elevation",
        "range_km",
        "cardinal_direction",
        "visible",
    }.issubset(payload)
    assert payload == expected_angles
    calculate_angles.assert_called_once_with(
        tle_line1=tle1,
        tle_line2=tle2,
        observer_lat=request_body["user_lat"],
        observer_lon=request_body["user_lon"],
    )


@pytest.mark.asyncio
async def test_observer_look_angles_invalid_tle(
    async_test_client: httpx.AsyncClient,
) -> None:
    """Reject short TLE query parameters before calculating observer angles."""
    response = await async_test_client.post(
        "/api/observer/look-angles",
        params={"tle1": "short", "tle2": "short"},
        json={
            "query": "look angles",
            "user_lat": 43.0008,
            "user_lon": -78.7889,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cors_preflight_headers(async_test_client: httpx.AsyncClient) -> None:
    """Allow a browser preflight request from the local Vite development origin."""
    response = await async_test_client.options(
        "/api/satellites/active",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin")