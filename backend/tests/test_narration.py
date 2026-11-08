"""Tests for POST /api/audio/narrate (single audio entry point)."""

from __future__ import annotations

import httpx
import pytest

BODY = {"object_name": "ISS", "object_type": "satellite"}


@pytest.mark.asyncio
async def test_narrate_returns_mp3(async_test_client, mock_elevenlabs_client):
    r = await async_test_client.post("/api/audio/narrate", json=BODY)
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3fake-mp3"


@pytest.mark.asyncio
async def test_repeat_requests_hit_cache(async_test_client, mock_elevenlabs_client):
    for _ in range(3):
        assert (await async_test_client.post("/api/audio/narrate", json=BODY)).status_code == 200
    assert mock_elevenlabs_client.call_count == 1


@pytest.mark.asyncio
async def test_cached_audio_works_without_api_key(async_test_client, mock_elevenlabs_client, monkeypatch):
    await async_test_client.post("/api/audio/narrate", json=BODY)  # warm cache
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    r = await async_test_client.post("/api/audio/narrate", json=BODY)
    assert r.status_code == 200 and r.content == b"ID3fake-mp3"


@pytest.mark.asyncio
async def test_provider_failure_is_json_502_not_empty_200(async_test_client, mock_elevenlabs_client):
    mock_elevenlabs_client.side_effect = lambda url, **kw: httpx.Response(
        401, text="bad key", request=httpx.Request("POST", url)
    )
    r = await async_test_client.post("/api/audio/narrate", json=BODY)
    assert r.status_code == 502
    assert "401" in r.json()["detail"]


@pytest.mark.asyncio
async def test_missing_key_is_502(async_test_client, mock_elevenlabs_client, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    r = await async_test_client.post("/api/audio/narrate", json=BODY)
    assert r.status_code == 502
    assert "ELEVENLABS_API_KEY" in r.json()["detail"]
