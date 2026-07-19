"""Ask-the-video: prompt assembly, citation mapping, API behaviour."""

import pytest
import respx
from httpx import Response
from fastapi.testclient import TestClient

import main
from summarize import ask, SummarizeError, _segment_index_for, _timestamp_to_seconds

client = TestClient(main.app)

SEGMENTS = [
    {"text": "intro", "start": 0.0, "duration": 10.0},
    {"text": "the middle part", "start": 10.0, "duration": 10.0},
    {"text": "conclusion", "start": 20.0, "duration": 10.0},
]


def groq_reply(payload: str):
    return Response(200, json={"choices": [{"message": {"content": payload}}]})


@pytest.mark.parametrize(
    "stamp,expected",
    [("0:05", 0), ("0:10", 1), ("0:15", 1), ("0:25", 2), ("1:00:00", 2)],
)
def test_segment_index_mapping(stamp, expected):
    assert _segment_index_for(_timestamp_to_seconds(stamp), SEGMENTS) == expected


def test_bad_timestamp_maps_to_none():
    assert _segment_index_for(_timestamp_to_seconds("garbage"), SEGMENTS) is None


@respx.mock
def test_prompt_contains_transcript_history_and_question():
    route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=groq_reply('{"answer": "a", "citations": [{"timestamp": "0:12"}]}')
    )
    result = ask(
        SEGMENTS, "what is the middle?", "groq", "k",
        history=[{"role": "user", "content": "earlier q"},
                 {"role": "assistant", "content": "earlier a"}],
    )
    sent = route.calls.last.request.content.decode()
    assert "the middle part" in sent          # transcript present
    assert "earlier q" in sent and "earlier a" in sent  # history folded in
    assert "what is the middle?" in sent      # question present
    # citation mapped to the right segment
    assert result["citations"] == [{"timestamp": "0:12", "segment_index": 1}]


@respx.mock
def test_refusal_passes_through_with_no_citations():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=groq_reply('{"answer": "The video doesn\'t cover that.", "citations": []}')
    )
    result = ask(SEGMENTS, "unrelated?", "groq", "k")
    assert "doesn't cover" in result["answer"]
    assert result["citations"] == []


def test_api_requires_question_and_segments():
    r = client.post("/api/ask", json={"question": "", "segments": SEGMENTS})
    assert r.status_code == 400
    r = client.post("/api/ask", json={"question": "hi?", "segments": []})
    assert r.status_code == 400
    assert "summarize" in r.json()["error"].lower()


def test_api_byok_routes_to_requested_provider(monkeypatch):
    seen = {}

    def fake_ask(segments, question, provider, key, **kw):
        seen.update(provider=provider, key=key, question=question,
                    history=kw.get("history"))
        return {"answer": "A", "citations": [], "model": "m", "provider": provider}

    monkeypatch.setattr(main, "ask", fake_ask)
    r = client.post(
        "/api/ask",
        json={
            "question": "Q?",
            "segments": SEGMENTS,
            "history": [{"role": "user", "content": "prev"}],
            "provider": "anthropic",
            "llm_key": "browser-key",
        },
    )
    assert r.status_code == 200
    assert seen["provider"] == "anthropic"
    assert seen["key"] == "browser-key"
    assert seen["history"] == [{"role": "user", "content": "prev"}]


def test_api_free_mode_fails_over_on_429(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g1")
    monkeypatch.setenv("GROQ_API_KEY", "g2")
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)
    calls = []

    def fake_ask(segments, question, provider, key, **kw):
        calls.append(provider)
        if provider == "gemini":
            raise SummarizeError("rate limit", status=429)
        return {"answer": "A", "citations": [], "model": "m", "provider": provider}

    monkeypatch.setattr(main, "ask", fake_ask)
    r = client.post("/api/ask", json={"question": "Q?", "segments": SEGMENTS})
    assert r.status_code == 200
    assert calls == ["gemini", "groq"]
