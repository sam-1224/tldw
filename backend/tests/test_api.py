"""API-level behaviour: BYOK override, free-mode failover, friendly errors."""

import pytest
from fastapi.testclient import TestClient

import main
from summarize import SummarizeError

client = TestClient(main.app)

TRANSCRIPT = {
    "segments": [{"text": "hi", "start": 0.0, "duration": 2.0}],
    "source": "captions",
}
SUMMARY = {"tldr": "t", "key_points": [], "topics": [], "truncated": False}
OEMBED = {"title": "T", "author": "A", "thumbnail": ""}


@pytest.fixture(autouse=True)
def stub_transcript(monkeypatch):
    monkeypatch.setattr(main, "get_transcript", lambda url, **kw: TRANSCRIPT)
    monkeypatch.setattr(main, "fetch_oembed", lambda vid: OEMBED)


def test_config_reports_free_chain_without_leaking_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    data = client.get("/api/config").json()
    assert data["free_tier_available"] is True
    assert data["free_chain"] == ["gemini"]
    assert "secret-value" not in str(data)
    ids = [p["id"] for p in data["providers"]]
    assert {"gemini", "groq", "openai", "anthropic", "xai", "custom"} <= set(ids)


def test_bad_url_400():
    r = client.post("/api/summarize", json={"url": "not a link"})
    assert r.status_code == 400


def test_keyless_no_env_key_friendly_400(monkeypatch):
    for p in ("GEMINI", "GROQ", "CEREBRAS"):
        monkeypatch.delenv(f"{p}_API_KEY", raising=False)
    r = client.post(
        "/api/summarize", json={"url": "https://youtu.be/dQw4w9WgXcQ"}
    )
    assert r.status_code == 400
    assert "free" in r.json()["error"].lower()


def test_byok_request_key_beats_env_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    seen = {}

    def fake_summarize(segments, provider, key, model=None, base_url=None):
        seen.update(provider=provider, key=key, model=model)
        return dict(SUMMARY)

    monkeypatch.setattr(main, "summarize", fake_summarize)
    r = client.post(
        "/api/summarize",
        json={
            "url": "https://youtu.be/dQw4w9WgXcQ",
            "provider": "openai",
            "llm_key": "browser-key",
            "model": "gpt-5.6",
        },
    )
    assert r.status_code == 200
    assert seen == {"provider": "openai", "key": "browser-key", "model": "gpt-5.6"}


def test_keyless_uses_env_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-gem")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    seen = {}

    def fake_summarize(segments, provider, key, model=None, base_url=None):
        seen.update(provider=provider, key=key)
        return dict(SUMMARY)

    monkeypatch.setattr(main, "summarize", fake_summarize)
    r = client.post("/api/summarize", json={"url": "https://youtu.be/dQw4w9WgXcQ"})
    assert r.status_code == 200
    assert seen == {"provider": "gemini", "key": "env-gem"}


def test_free_mode_fails_over_on_429(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-gem")
    monkeypatch.setenv("GROQ_API_KEY", "env-groq")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    calls = []

    def fake_summarize(segments, provider, key, model=None, base_url=None):
        calls.append(provider)
        if provider == "gemini":
            raise SummarizeError("gemini rate limit hit.", status=429)
        return dict(SUMMARY)

    monkeypatch.setattr(main, "summarize", fake_summarize)
    r = client.post("/api/summarize", json={"url": "https://youtu.be/dQw4w9WgXcQ"})
    assert r.status_code == 200
    assert calls == ["gemini", "groq"]


def test_byok_does_not_fail_over(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-groq")

    def fake_summarize(segments, provider, key, model=None, base_url=None):
        raise SummarizeError("gemini rate limit hit.", status=429)

    monkeypatch.setattr(main, "summarize", fake_summarize)
    r = client.post(
        "/api/summarize",
        json={
            "url": "https://youtu.be/dQw4w9WgXcQ",
            "provider": "gemini",
            "llm_key": "my-key",
        },
    )
    assert r.status_code == 502


def test_custom_base_url_passes_through(monkeypatch):
    seen = {}

    def fake_summarize(segments, provider, key, model=None, base_url=None):
        seen.update(provider=provider, key=key, base_url=base_url)
        return dict(SUMMARY)

    monkeypatch.setattr(main, "summarize", fake_summarize)
    r = client.post(
        "/api/summarize",
        json={
            "url": "https://youtu.be/dQw4w9WgXcQ",
            "provider": "custom",
            "base_url": "http://localhost:11434/v1",
            "model": "llama3",
        },
    )
    assert r.status_code == 200
    assert seen["base_url"] == "http://localhost:11434/v1"
    assert seen["key"] == ""
