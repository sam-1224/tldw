"""
Provider-agnostic summarisation.

One tiny function talks to whichever LLM the user picked. We use plain HTTP
(httpx) instead of four separate SDKs so the dependency list stays short and
the code is easy to read and fork.

Supported providers: anthropic, openai, gemini, groq.
The model for each is overridable, but sensible cheap defaults are baked in.
"""

from __future__ import annotations

import json
import re
import httpx

DEFAULT_MODELS = {
    "anthropic": "claude-3-5-haiku-latest",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-1.5-flash",
    "groq": "llama-3.3-70b-versatile",
}

# Keep prompts affordable. Most transcripts fit; very long ones get trimmed.
MAX_CHARS = 48_000


class SummarizeError(Exception):
    pass


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


def _call_openai_compatible(prompt: str, key: str, model: str, base: str) -> str:
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        },
        timeout=120.0,
    )
    _raise_for_llm(r, "provider")
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
        raise SummarizeError(f"That {provider} API key was rejected.")
    if resp.status_code == 429:
        raise SummarizeError(f"{provider} rate limit hit. Try again in a moment.")
    if resp.status_code >= 400:
        raise SummarizeError(
            f"{provider} request failed ({resp.status_code}). "
            "Check the model name and your key."
        )


def summarize(
    segments: list[dict],
    provider: str,
    api_key: str,
    model: str | None = None,
) -> dict:
    provider = (provider or "").lower()
    if provider not in DEFAULT_MODELS:
        raise SummarizeError(f"Unknown provider '{provider}'.")
    if not api_key:
        raise SummarizeError("No LLM API key provided.")

    model = model or DEFAULT_MODELS[provider]
    text, truncated = build_timestamped_text(segments)
    prompt = (
        f"Transcript{' (truncated to keep cost down)' if truncated else ''}:\n\n"
        f"{text}"
    )

    if provider == "anthropic":
        raw = _call_anthropic(prompt, api_key, model)
    elif provider == "openai":
        raw = _call_openai_compatible(prompt, api_key, model, "https://api.openai.com/v1")
    elif provider == "groq":
        raw = _call_openai_compatible(prompt, api_key, model, "https://api.groq.com/openai/v1")
    elif provider == "gemini":
        raw = _call_gemini(prompt, api_key, model)

    result = _extract_json(raw)
    result["truncated"] = truncated
    result["model"] = model
    return result
