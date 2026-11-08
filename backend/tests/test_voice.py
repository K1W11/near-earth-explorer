import httpx
import pytest

from audio import voice


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(voice, "AUDIO_DIR", tmp_path)


def fake_post(calls):
    def post(url, **kw):
        calls.append((url, kw))
        return httpx.Response(200, content=b"ID3fake", request=httpx.Request("POST", url))
    return post


def test_cache_hit_calls_api_once(monkeypatch):
    calls = []
    monkeypatch.setattr(voice.httpx, "post", fake_post(calls))
    a = voice.narrate("Hello   world")
    b = voice.narrate("Hello world")  # whitespace-normalised -> same file
    assert a == b and a.read_bytes() == b"ID3fake"
    assert len(calls) == 1
    assert calls[0][1]["headers"]["xi-api-key"] == "test-key"


def test_empty_and_too_long_rejected():
    with pytest.raises(voice.AudioError):
        voice.narrate("   ")
    with pytest.raises(voice.AudioError):
        voice.narrate("x" * (voice.MAX_CHARS + 1))


def test_missing_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    with pytest.raises(voice.AudioError):
        voice.narrate("hi")


def test_api_error_wrapped(monkeypatch):
    def boom(url, **kw):
        return httpx.Response(401, text="bad key", request=httpx.Request("POST", url))
    monkeypatch.setattr(voice.httpx, "post", boom)
    with pytest.raises(voice.AudioError, match="401"):
        voice.narrate("hi")
