"""
TL;DW — FastAPI backend.

Endpoints:
  GET  /                -> serves the single-file frontend
  GET  /api/health      -> liveness check
  GET  /api/config      -> provider/model catalog + free-tier availability
  POST /api/summarize   -> { url, provider?, llm_key?, supadata_key?, model?, base_url? }

Key resolution, in order:
  1. BYOK — a key in the request body always wins and is used only for the
     provider the user picked. Never logged, never persisted.
  2. Free mode — keyless requests fall back to server env keys, trying the
     FREE_CHAIN providers in order and failing over on rate limits so
     visitors need zero setup.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env is explicit user intent for THIS app — let it beat stale
# machine-wide env vars (a leftover global GEMINI_API_KEY etc.).
load_dotenv(Path(__file__).parent / ".env", override=True)

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from transcript import (
    get_transcript,
    fetch_oembed,
    extract_video_id,
    TranscriptError,
)
from summarize import summarize, SummarizeError, PROVIDERS, SUMMARY_LANGUAGES

app = FastAPI(title="TL;DW", description="Too long; didn't watch.")

_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
FRONTEND_DIST = _FRONTEND_DIR / "dist"
FRONTEND_LEGACY = _FRONTEND_DIR / "legacy" / "index.html"

if (FRONTEND_DIST / "assets").is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets"
    )

# Free-mode failover order. Only providers with an env key participate.
FREE_CHAIN = ["gemini", "groq", "cerebras"]


def _env_key(provider: str) -> str:
    return os.getenv(f"{provider.upper()}_API_KEY") or ""


def _default_provider() -> str:
    return (os.getenv("DEFAULT_PROVIDER") or "gemini").lower()


class SummarizeRequest(BaseModel):
    url: str
    provider: str | None = None
    llm_key: str | None = None
    supadata_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    summary_lang: str | None = None
    lang: str = "en"


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def config():
    """Provider catalog for the frontend. Key PRESENCE only — never values."""
    free_chain = [p for p in FREE_CHAIN if _env_key(p)]
    return {
        "free_tier_available": bool(free_chain),
        "default_provider": _default_provider(),
        "free_chain": free_chain,
        "summary_languages": SUMMARY_LANGUAGES,
        "providers": [
            {
                "id": pid,
                "label": cfg["label"],
                "default_model": cfg["default_model"],
                "models": cfg["models"],
                "key_optional": bool(cfg.get("key_optional")),
                "needs_base_url": pid == "custom",
            }
            for pid, cfg in PROVIDERS.items()
        ],
    }


@app.get("/")
def index():
    # Built React app when present; pre-Stage-2 static file as fallback.
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    if FRONTEND_LEGACY.exists():
        return FileResponse(FRONTEND_LEGACY)
    return JSONResponse({"error": "frontend not found"}, status_code=404)


def build_llm_attempts(
    provider: str, llm_key: str | None, base_url: str | None
) -> list[tuple[str, str, str | None]]:
    """(provider, key, base_url) attempts — the shared seam for /api/summarize
    and future endpoints (/api/ask). BYOK pins one attempt; free mode walks
    the env-keyed chain so rate limits fail over."""
    if llm_key or base_url:
        return [(provider, llm_key or "", base_url)]
    chain = [provider] + [p for p in FREE_CHAIN if p != provider]
    return [(p, _env_key(p), None) for p in chain if _env_key(p)]


NO_KEY_MESSAGE = (
    "This server has no free-tier key configured and you didn't add your own. "
    "Add a key in settings — free ones take ~2 minutes: Gemini "
    "(aistudio.google.com), Groq (console.groq.com), or OpenRouter "
    "(openrouter.ai)."
)


@app.post("/api/summarize")
def do_summarize(req: SummarizeRequest):
    video_id = extract_video_id(req.url)
    if not video_id:
        return JSONResponse(
            {"error": "That doesn't look like a YouTube link."}, status_code=400
        )

    provider = (req.provider or _default_provider()).lower()
    attempts = build_llm_attempts(provider, req.llm_key, req.base_url)
    if not attempts:
        return JSONResponse({"error": NO_KEY_MESSAGE}, status_code=400)

    supadata_key = req.supadata_key or os.getenv("SUPADATA_API_KEY") or None

    # 1. Transcript (free library -> optional Supadata fallback).
    try:
        tr = get_transcript(req.url, supadata_key=supadata_key, lang=req.lang)
    except TranscriptError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    segments = tr["segments"]
    duration = max((s["start"] + s["duration"] for s in segments), default=0.0)

    # 2. Summary (chosen LLM, with free-mode failover on 429).
    summary = None
    last_error: SummarizeError | None = None
    for attempt_provider, key, base_url in attempts:
        try:
            # Only pass the model through for the provider the user picked;
            # failover providers use their own defaults.
            model = req.model if attempt_provider == provider else None
            summary = summarize(
                segments, attempt_provider, key, model=model, base_url=base_url,
                summary_lang=req.summary_lang,
            )
            break
        except SummarizeError as exc:
            last_error = exc
            if exc.status in (429, 413) and len(attempts) > 1:
                continue  # rate-limited / too large -> try next in chain
            return JSONResponse({"error": str(exc)}, status_code=502)
    if summary is None:
        return JSONResponse({"error": str(last_error)}, status_code=502)

    meta = fetch_oembed(video_id)

    return {
        "video_id": video_id,
        "duration_seconds": duration,
        "transcript_source": tr["source"],
        "transcript_language": tr.get("language", "en"),
        "title": meta["title"],
        "author": meta["author"],
        "thumbnail": meta["thumbnail"],
        "summary": summary,
        "segments": segments,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
