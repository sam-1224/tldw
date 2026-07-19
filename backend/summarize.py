"""
Provider-agnostic summarisation.

One tiny function talks to whichever LLM the user picked. We use plain HTTP
(httpx) instead of separate SDKs so the dependency list stays short and the
code is easy to read and fork.

Providers live in PROVIDERS below. Most frontier APIs speak the OpenAI
chat-completions dialect, so one generic call covers them; Anthropic and
Gemini keep dedicated request shapes. The `custom` provider takes any
OpenAI-compatible base_url (Ollama, LM Studio, vLLM, ...) with an optional key.

Model catalogs are data, not architecture: edit PROVIDERS when models change.
Free-text model override is always honoured.
"""

from __future__ import annotations

import json
import re
import httpx

# kind: "oai" = OpenAI-compatible chat/completions; others have dedicated calls.
# models: leading choices surfaced in the UI dropdown (free-text override kept).
# Model ids verified July 2026 — update here when providers rotate models.
PROVIDERS: dict[str, dict] = {
    "gemini": {
        "label": "Google Gemini",
        "kind": "gemini",
        # "-latest" aliases track Google's current models; fixed ids get
        # withdrawn for new API keys ("no longer available to new users").
        "default_model": "gemini-flash-latest",
        "models": [
            "gemini-flash-latest",
            "gemini-3-flash-preview",
            "gemini-flash-lite-latest",
            "gemini-pro-latest",
        ],
    },
    "groq": {
        "label": "Groq (fast open models)",
        "kind": "oai",
        "base": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
        ],
    },
    "cerebras": {
        "label": "Cerebras (fast open models)",
        "kind": "oai",
        "base": "https://api.cerebras.ai/v1",
        "default_model": "llama-3.3-70b",
        "models": ["llama-3.3-70b", "llama3.1-8b", "gpt-oss-120b", "qwen-3-32b"],
    },
    "openai": {
        "label": "OpenAI",
        "kind": "oai",
        "base": "https://api.openai.com/v1",
        "default_model": "gpt-5.6",
        "models": ["gpt-5.6", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-4.1-mini"],
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "kind": "anthropic",
        "default_model": "claude-sonnet-5",
        "models": [
            "claude-sonnet-5",
            "claude-fable-5",
            "claude-opus-4-8",
            "claude-haiku-4-5",
        ],
    },
    "xai": {
        "label": "xAI Grok",
        "kind": "oai",
        "base": "https://api.x.ai/v1",
        "default_model": "grok-4-fast",
        "models": ["grok-4-fast", "grok-4-5", "grok-4", "grok-3-mini"],
    },
    "moonshot": {
        "label": "Moonshot Kimi",
        "kind": "oai",
        "base": "https://api.moonshot.ai/v1",
        "default_model": "kimi-k3",
        "models": ["kimi-k3", "kimi-k2.6"],
    },
    "deepseek": {
        "label": "DeepSeek",
        "kind": "oai",
        "base": "https://api.deepseek.com/v1",
        "default_model": "deepseek-v4-flash",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
    },
    "openrouter": {
        "label": "OpenRouter",
        "kind": "oai",
        "base": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "models": ["meta-llama/llama-3.3-70b-instruct:free"],
    },
    "custom": {
        "label": "Custom / local (OpenAI-compatible)",
        "kind": "oai",
        "base": None,  # supplied per-request (e.g. http://localhost:11434/v1)
        "default_model": "",
        "models": [],
        "key_optional": True,
    },
}

# Keep prompts affordable. Most transcripts fit; very long ones get trimmed.
MAX_CHARS = 48_000


class SummarizeError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_timestamped_text(segments: list[dict]) -> tuple[str, bool]:
    """Turn segments into '[mm:ss] text' lines the model can anchor points to."""
    lines = []
    for seg in segments:
        lines.append(f"[{_format_timestamp(seg['start'])}] {seg['text']}")
    text = "\n".join(lines)
    truncated = False
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        truncated = True
    return text, truncated


SYSTEM_PROMPT = (
    "You are a precise video summariser. You are given a YouTube transcript "
    "where each line is prefixed with a [timestamp]. Produce a faithful, "
    "skimmable summary. Anchor each key point to the timestamp where that "
    "topic begins, copied from the transcript. Never invent timestamps or "
    "facts. Respond with ONLY a JSON object, no markdown, no preamble, in "
    "exactly this shape:\n"
    "{\n"
    '  "tldr": "one or two sentence gist",\n'
    '  "key_points": [\n'
    '    {"timestamp": "m:ss", "point": "what is covered here"}\n'
    "  ],\n"
    '  "topics": ["short tag", "short tag"]\n'
    "}\n"
    "Aim for 4-8 key points. Keep each point to one sentence."
)


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Strip ```json fences if a model adds them despite instructions.
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost { ... }.
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise SummarizeError("Model did not return valid JSON.")


def _call_anthropic(prompt: str, key: str, model: str) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1500,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120.0,
    )
    _raise_for_llm(r, "anthropic")
    data = r.json()
    return "".join(b.get("text", "") for b in data.get("content", []))


def _call_openai_compatible(
    prompt: str, key: str, model: str, base: str, provider: str, json_mode: bool = True
) -> str:
    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    # Local servers (Ollama/LM Studio) don't all accept response_format.
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    r = httpx.post(f"{base}/chat/completions", headers=headers, json=body, timeout=120.0)
    _raise_for_llm(r, provider)
    return r.json()["choices"][0]["message"]["content"]


def _call_gemini(prompt: str, key: str, model: str) -> str:
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key},
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        },
        timeout=120.0,
    )
    _raise_for_llm(r, "gemini")
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _raise_for_llm(resp: httpx.Response, provider: str) -> None:
    if resp.status_code == 401:
        raise SummarizeError(f"That {provider} API key was rejected.", status=401)
    if resp.status_code == 429:
        raise SummarizeError(
            f"{provider} rate limit hit. Try again in a moment.", status=429
        )
    if resp.status_code >= 400:
        raise SummarizeError(
            f"{provider} request failed ({resp.status_code}). "
            "Check the model name and your key.",
            status=resp.status_code,
        )


def summarize(
    segments: list[dict],
    provider: str,
    api_key: str,
    model: str | None = None,
    base_url: str | None = None,
) -> dict:
    provider = (provider or "").lower()
    cfg = PROVIDERS.get(provider)
    if cfg is None:
        raise SummarizeError(f"Unknown provider '{provider}'.")
    if not api_key and not cfg.get("key_optional"):
        raise SummarizeError("No LLM API key provided.")

    model = model or cfg["default_model"]
    if not model:
        raise SummarizeError(f"Provider '{provider}' needs a model name.")

    text, truncated = build_timestamped_text(segments)
    prompt = (
        f"Transcript{' (truncated to keep cost down)' if truncated else ''}:\n\n"
        f"{text}"
    )

    kind = cfg["kind"]
    if kind == "anthropic":
        raw = _call_anthropic(prompt, api_key, model)
    elif kind == "gemini":
        raw = _call_gemini(prompt, api_key, model)
    else:  # OpenAI-compatible
        base = base_url or cfg["base"]
        if not base:
            raise SummarizeError("Custom provider needs a base URL.")
        raw = _call_openai_compatible(
            prompt, api_key, model, base.rstrip("/"),
            provider, json_mode=provider != "custom",
        )

    result = _extract_json(raw)
    result["truncated"] = truncated
    result["model"] = model
    result["provider"] = provider
    return result
