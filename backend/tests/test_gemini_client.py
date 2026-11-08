"""Tests for secure Gemini client configuration and initialization."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock
from unittest.mock import AsyncMock

import httpx
import pytest

import gemini_client


def test_gemini_client_initializes_once_with_configured_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create one shared SDK client when a key is available."""
    monkeypatch.setattr(gemini_client, "_client", None)
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    expected_client = mock.MagicMock()

    with mock.patch(
        "gemini_client.genai.Client",
        return_value=expected_client,
    ) as client_factory:
        first_client = gemini_client.get_gemini_client()
        second_client = gemini_client.get_gemini_client()

    assert first_client is expected_client
    assert second_client is expected_client
    client_factory.assert_called_once_with(
        api_key="unit-test-key",
        http_options=mock.ANY,
    )


def test_gemini_client_raises_clear_error_when_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise an actionable configuration error without exposing credentials."""
    monkeypatch.setattr(gemini_client, "_client", None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(
        gemini_client.GeminiConfigurationError,
        match="GEMINI_API_KEY is not configured",
    ):
        gemini_client.get_gemini_client()


@pytest.mark.asyncio
async def test_assistant_response_does_not_expose_configured_api_key(
    async_test_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep configured credentials out of assistant API responses."""
    api_key = "unit-test-secret"
    monkeypatch.setattr(gemini_client, "_client", None)
    monkeypatch.setenv("GEMINI_API_KEY", api_key)

    with (
        mock.patch(
            "gemini_client.genai.Client",
            return_value=mock.MagicMock(),
        ) as client_factory,
        mock.patch(
            "main._generate_content",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(
                function_calls=None,
                text="The Moon is Earth's only natural satellite.",
            ),
        ),
    ):
        response = await async_test_client.post(
            "/api/assistant/query",
            json={"query": "What is the Moon?"},
        )

    assert response.status_code == 200
    assert api_key not in response.text
    client_factory.assert_called_once_with(
        api_key=api_key,
        http_options=mock.ANY,
    )


def test_gemini_client_does_not_infer_vertex_mode_from_key_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Key prefixes do not override the configured Developer API endpoint."""
    monkeypatch.setattr(gemini_client, "_client", None)
    monkeypatch.setenv("GEMINI_API_KEY", "AQ.fake-express-key")
    monkeypatch.delenv("GEMINI_USE_VERTEX", raising=False)
    monkeypatch.delenv("GEMINI_API_VERSION", raising=False)

    with mock.patch("gemini_client.genai.Client") as client_factory:
        gemini_client.get_gemini_client()

    client_factory.assert_called_once_with(api_key="AQ.fake-express-key", http_options=mock.ANY)
