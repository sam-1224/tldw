"""Provider registry routing + error mapping."""

import pytest
import respx
from httpx import Response

from summarize import summarize, SummarizeError, PROVIDERS

SEGMENTS = [{"text": "hello world", "start": 0.0, "duration": 2.0}]
GOOD_JSON = '{"tldr": "t", "key_points": [{"timestamp": "0:00", "point": "p"}], "topics": ["x"]}'

OAI_PROVIDERS = {
    pid: cfg for pid, cfg in PROVIDERS.items() if cfg["kind"] == "oai" and cfg["base"]
}


def oai_body():
    return {"choices": [{"message": {"content": GOOD_JSON}}]}


@respx.mock
@pytest.mark.parametrize("pid", list(OAI_PROVIDERS))
def test_oai_provider_routes_to_its_base_url(pid):
    cfg = OAI_PROVIDERS[pid]
    route = respx.post(f"{cfg['base']}/chat/completions").mock(
        return_value=Response(200, json=oai_body())
    )
    result = summarize(SEGMENTS, pid, "test-key")
    assert route.called
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer test-key"
    assert result["tldr"] == "t"
    assert result["provider"] == pid
    assert result["model"] == cfg["default_model"]


@respx.mock
def test_anthropic_routing_and_auth_header():
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(200, json={"content": [{"text": GOOD_JSON}]})
    )
    result = summarize(SEGMENTS, "anthropic", "ant-key", model="claude-sonnet-5")
    assert route.calls.last.request.headers["x-api-key"] == "ant-key"
    assert result["model"] == "claude-sonnet-5"


@respx.mock
def test_gemini_routing_key_in_query():
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ).mock(
        return_value=Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": GOOD_JSON}]}}]},
        )
    )
    summarize(SEGMENTS, "gemini", "gem-key")
    assert "key=gem-key" in str(route.calls.last.request.url)


@respx.mock
def test_custom_base_url_key_optional():
    route = respx.post("http://localhost:11434/v1/chat/completions").mock(
        return_value=Response(200, json=oai_body())
    )
    result = summarize(
        SEGMENTS, "custom", "", model="llama3", base_url="http://localhost:11434/v1"
    )
    assert route.called
    assert "Authorization" not in route.calls.last.request.headers
    # local servers don't all accept response_format — must be omitted
    assert b"response_format" not in route.calls.last.request.content
    assert result["model"] == "llama3"


def test_custom_without_base_url_errors():
    with pytest.raises(SummarizeError, match="base URL"):
        summarize(SEGMENTS, "custom", "", model="llama3")


def test_unknown_provider():
    with pytest.raises(SummarizeError, match="Unknown provider"):
        summarize(SEGMENTS, "nope", "key")


def test_missing_key_for_key_required_provider():
    with pytest.raises(SummarizeError, match="No LLM API key"):
        summarize(SEGMENTS, "openai", "")


@respx.mock
@pytest.mark.parametrize(
    "status,match", [(401, "rejected"), (429, "rate limit"), (500, "failed")]
)
def test_error_mapping(status, match):
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=Response(status, json={})
    )
    with pytest.raises(SummarizeError, match=match) as exc_info:
        summarize(SEGMENTS, "groq", "k")
    assert exc_info.value.status == status
