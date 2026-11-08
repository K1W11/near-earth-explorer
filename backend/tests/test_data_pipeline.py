"""Tests for NASA NeoWs and CelesTrak ingestion and TTL cache behavior."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Generator
from unittest import mock
from unittest.mock import AsyncMock

import httpx
import pytest

import data_pipeline


@pytest.fixture(autouse=True)
def clear_pipeline_state() -> Generator[None, None, None]:
    """Keep process-global cache entries and asyncio locks isolated per test."""
    data_pipeline._cache.clear()
    data_pipeline._cache_locks.clear()
    yield
    data_pipeline._cache.clear()
    data_pipeline._cache_locks.clear()


def _json_response(payload: dict[str, Any]) -> mock.Mock:
    """Build the small HTTP response interface consumed by the NeoWs fetcher."""
    response = mock.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.mark.asyncio
async def test_fetch_asteroids_success_and_parsing(
    mock_nasa_payload: dict[str, Any],
) -> None:
    """Parse NeoWs records, verify normalized fields, and check distance sorting."""
    payload = deepcopy(mock_nasa_payload)
    original = payload["near_earth_objects"]["2026-11-07"][0]
    farther_asteroid = deepcopy(original)
    farther_asteroid["id"] = "9999999"
    farther_asteroid["name"] = "Farther test asteroid"
    farther_asteroid["close_approach_data"][0]["miss_distance"]["kilometers"] = (
        "3000000.0"
    )
    payload["near_earth_objects"]["2026-11-07"].append(farther_asteroid)
    response = _json_response(payload)

    with mock.patch(
        "data_pipeline.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=response,
    ) as get:
        asteroids = await data_pipeline.fetch_asteroids()

    distances = [asteroid["miss_distance_km"] for asteroid in asteroids]
    assert distances == sorted(distances)
    assert distances[0] < distances[1]
    assert asteroids[0]["id"] == "2465633"
    assert {
        "id",
        "name",
        "estimated_diameter_km",
        "is_potentially_hazardous_asteroid",
        "close_approach_date_full",
        "miss_distance_km",
        "relative_velocity_kmh",
    }.issubset(asteroids[0])
    assert asteroids[0]["estimated_diameter_km"] == 0.41
    assert len(f"{asteroids[0]['estimated_diameter_km']:.3f}".split(".")[1]) == 3
    get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_asteroids_cache_hit(
    mock_nasa_payload: dict[str, Any],
) -> None:
    """Make two same-window requests and verify the second uses the TTL cache."""
    response = _json_response(mock_nasa_payload)
    with mock.patch(
        "data_pipeline.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=response,
    ) as get:
        first_result = await data_pipeline.fetch_asteroids()
        second_result = await data_pipeline.fetch_asteroids()

    assert second_result == first_result
    get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_asteroids_cache_expiration(
    mock_nasa_payload: dict[str, Any],
    mock_time: mock.MagicMock,
) -> None:
    """Advance the patched wall clock beyond TTL and verify the feed is refetched."""
    response = _json_response(mock_nasa_payload)
    with mock.patch(
        "data_pipeline.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=response,
    ) as get:
        await data_pipeline.fetch_asteroids()
        assert get.await_count == 1

        # ``mock_time`` controls the timestamp written into the cache. Advance
        # it beyond CACHE_TTL so the next call must fetch rather than reuse.
        mock_time.return_value += data_pipeline.CACHE_TTL + 1
        await data_pipeline.fetch_asteroids()

    assert get.await_count == 2


@pytest.mark.asyncio
async def test_fetch_asteroids_stampede_lock(
    mock_nasa_payload: dict[str, Any],
) -> None:
    """Collapse thirty simultaneous cold-cache requests into one HTTP fetch."""
    response = _json_response(mock_nasa_payload)

    async def delayed_response(*args: Any, **kwargs: Any) -> mock.Mock:
        """Simulate an upstream network delay while other tasks contend on cache."""
        await asyncio.sleep(0.05)
        assert args[0] == data_pipeline.NASA_FEED_URL
        assert kwargs["params"]["api_key"] == "DEMO_KEY"
        return response

    with mock.patch(
        "data_pipeline.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=delayed_response,
    ) as get:
        results = await asyncio.gather(
            *(data_pipeline.fetch_asteroids() for _ in range(30))
        )

    assert all(result == results[0] for result in results)
    get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_active_satellites_parsing(
    mock_celestrak_payload: str,
) -> None:
    """Parse the CelesTrak three-line ISS record into name and TLE fields."""
    response = mock.Mock()
    response.text = mock_celestrak_payload
    response.raise_for_status.return_value = None

    with mock.patch(
        "data_pipeline.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        return_value=response,
    ) as get:
        satellites = await data_pipeline.fetch_active_satellites()

    assert isinstance(satellites, list)
    assert satellites
    assert all({"name", "tle1", "tle2"}.issubset(satellite) for satellite in satellites)
    assert satellites[0]["name"] == "ISS (ZARYA)"
    assert satellites[0]["tle1"].startswith("1 ")
    assert satellites[0]["tle2"].startswith("2 ")
    get.assert_awaited_once()


def test_parse_asteroid_feed_malformed_json() -> None:
    """Report a clear error if a NASA response lacks its required object map."""
    with pytest.raises(
        ValueError,
        match="NASA NeoWs response is missing near_earth_objects",
    ):
        data_pipeline._parse_asteroid_feed({})


@pytest.mark.asyncio
async def test_upstream_http_error_handling() -> None:
    """Propagate upstream HTTP errors and leave failed responses uncached."""
    request = httpx.Request("GET", data_pipeline.NASA_FEED_URL)
    response = httpx.Response(
        status_code=500,
        request=request,
        text="Upstream failure",
    )
    upstream_error = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=request,
        response=response,
    )

    with mock.patch(
        "data_pipeline.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=upstream_error,
    ) as get:
        with pytest.raises(httpx.HTTPError):
            await data_pipeline.fetch_asteroids()

    get.assert_awaited_once()
    assert "asteroids" not in data_pipeline._cache