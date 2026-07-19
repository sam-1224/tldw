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
        # Free tier allows ~6k tokens/min; keep prompt ~4.5k tokens so the
        # request fits (rest is system prompt + completion headroom).
        "max_chars": 18_000,
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


def build_timestamped_text(
    segments: list[dict], max_chars: int = MAX_CHARS
) -> tuple[str, bool]:
    """Turn segments into '[mm:ss] text' lines the model can anchor points to."""
    lines = []
    for seg in segments:
        lines.append(f"[{_format_timestamp(seg['start'])}] {seg['text']}")
    text = "\n".join(lines)
    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True
    return text, truncated


SYSTEM_PROMPT = (
    "You are a precise video summariser. You are given a YouTube transcript "
    "where each line is prefixed with a [timestamp]. Produce a faithful, "
    "skimmable, genuinely useful summary. Anchor each key point to the "
    "timestamp where that topic begins, copied from the transcript. Never "
    "invent timestamps or facts. Respond with ONLY a JSON object, no "
    "markdown, no preamble, in exactly this shape:\n"
    "{\n"
    '  "tldr": "two or three sentence gist of the whole video",\n'
    '  "breakdown": [\n'
    '    "a short paragraph of narrative summary",\n'
    '    "another short paragraph"\n'
    "  ],\n"
    '  "key_points": [\n'
    '    {"timestamp": "m:ss", "point": "one-line headline of this moment",\n'
    '     "detail": "one or two sentences of what is actually said or shown"}\n'
    "  ],\n"
    '  "takeaways": ["something the viewer should remember or act on"],\n'
    '  "worth_watching": {"score": 7, "reason": "one line on who should '
    'watch and what to skip"},\n'
    '  "topics": ["short tag", "short tag"]\n'
    "}\n"
    "Rules: breakdown is 2-4 paragraphs covering the video's actual "
    "argument or content, not topic labels. Aim for 5-10 key_points; the "
    "point is a headline, the detail adds substance. takeaways is 3-5 "
    "bullets of distilled insight. worth_watching.score is 1-10 judging "
    "information density and originality of the video itself. The transcript "
    "may be in any language — write every text field of the summary in "
    "{output_language}, translating faithfully. Keys and timestamps stay "
    "as specified."
)

# UI dropdown options; any BCP-47-ish name works since it's passed as text.
SUMMARY_LANGUAGES = [
    "English", "हिन्दी (Hindi)", "Español", "Français", "Deutsch",
    "Português", "Italiano", "日本語 (Japanese)", "한국어 (Korean)",
    "中文 (Chinese)", "Русский (Russian)", "العربية (Arabic)",
    "Bahasa Indonesia", "Türkçe", "same language as the video",
]


def _system_prompt(summary_lang: str | None) -> str:
    return SYSTEM_PROMPT.replace("{output_language}", summary_lang or "English")


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Strip ```json fences if a model adds them despite instructions.
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Last resort: grab the outermost { ... }.
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise SummarizeError("Model did not return valid JSON.")


def _call_anthropic(prompt: str, key: str, model: str, system: str) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 3000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120.0,
    )
    _raise_for_llm(r, "anthropic")
    data = r.json()
    return "".join(b.get("text", "") for b in data.get("content", []))


def _call_openai_compatible(
    prompt: str, key: str, model: str, base: str, provider: str, system: str,
    json_mode: bool = True,
) -> str:
    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        # Cap the completion: providers like Groq count RESERVED completion
        # tokens against rate limits, and an unset max lets them assume the
        # model maximum (instant 413 on free tiers).
        "max_tokens": 3000,
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


def _call_gemini(prompt: str, key: str, model: str, system: str) -> str:
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key},
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": system}]},
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
    if resp.status_code == 413:
        raise SummarizeError(
            f"Transcript too large for {provider}'s free tier. Pick another "
            "model or let Auto route it.", status=413
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
    summary_lang: str | None = None,
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

    kind = cfg["kind"]
    system = _system_prompt(summary_lang)

    def _call(prompt: str) -> str:
        if kind == "anthropic":
            return _call_anthropic(prompt, api_key, model, system)
        if kind == "gemini":
            return _call_gemini(prompt, api_key, model, system)
        base = base_url or cfg["base"]
        if not base:
            raise SummarizeError("Custom provider needs a base URL.")
        return _call_openai_compatible(
            prompt, api_key, model, base.rstrip("/"), provider, system,
            json_mode=provider != "custom",
        )

    # Adaptive retries:
    # - 413 (request too large): per-model TPM limits vary and chars/token
    #   depends on the language -> halve the transcript and try again.
    # - broken JSON from the model -> one straight retry.
    max_chars = cfg.get("max_chars", MAX_CHARS)
    result = truncated = None
    for shrink in range(3):
        text, truncated = build_timestamped_text(segments, max_chars=max_chars)
        prompt = (
            f"Transcript{' (truncated to keep cost down)' if truncated else ''}"
            f":\n\n{text}"
        )
        try:
            for attempt in range(2):
                raw = _call(prompt)
                try:
                    result = _extract_json(raw)
                    break
                except SummarizeError:
                    if attempt:
                        raise
            break
        except SummarizeError as exc:
            if exc.status == 413 and shrink < 2:
                max_chars //= 2
                continue
            raise
    # Weaker models sometimes drop contract fields — normalise so consumers
    # never KeyError and the UI just hides empty sections.
    result.setdefault("tldr", "")
    result.setdefault("key_points", [])
    result.setdefault("breakdown", [])
    result.setdefault("takeaways", [])
    result.setdefault("topics", [])
    result["truncated"] = truncated
    result["model"] = model
    result["provider"] = provider
    return result
