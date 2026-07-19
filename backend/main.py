"""
TL;DW — FastAPI backend.

Endpoints:
  GET  /                -> serves the single-file frontend
  GET  /api/health      -> liveness check
  POST /api/summarize   -> { url, provider, llm_key?, supadata_key?, model? }

Keys: a request may carry its own keys (BYOK from the browser). If it doesn't,
the server falls back to environment variables. This makes both self-hosting
(.env) and bring-your-own-key (browser) work from the same code.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from transcript import (
    get_transcript,
    fetch_oembed,
    extract_video_id,
    TranscriptError,
)
from summarize import summarize, SummarizeError

app = FastAPI(title="TL;DW", description="Too long; didn't watch.")

FRONTEND = Path(__file__).parent.parent / "frontend" / "index.html"


class SummarizeRequest(BaseModel):
    url: str
    provider: str = "anthropic"
    llm_key: str | None = None
    supadata_key: str | None = None
    model: str | None = None
    lang: str = "en"


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    if FRONTEND.exists():
        return FileResponse(FRONTEND)
    return JSONResponse({"error": "frontend not found"}, status_code=404)


@app.post("/api/summarize")
def do_summarize(req: SummarizeRequest):
    # Resolve keys: request wins, environment is the fallback.
    llm_key = req.llm_key or os.getenv(f"{req.provider.upper()}_API_KEY") or ""
    supadata_key = req.supadata_key or os.getenv("SUPADATA_API_KEY") or None

    video_id = extract_video_id(req.url)
    if not video_id:
        return JSONResponse(
            {"error": "That doesn't look like a YouTube link."}, status_code=400
        )
    if not llm_key:
        return JSONResponse(
            {"error": f"No API key for {req.provider}. Add one in settings."},
            status_code=400,
        )

    # 1. Transcript (free library -> optional Supadata fallback).
    try:
        tr = get_transcript(req.url, supadata_key=supadata_key, lang=req.lang)
    except TranscriptError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    segments = tr["segments"]
    duration = max((s["start"] + s["duration"] for s in segments), default=0.0)

    # 2. Summary (chosen LLM).
    try:
        summary = summarize(segments, req.provider, llm_key, model=req.model)
    except SummarizeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)

    meta = fetch_oembed(video_id)

    return {
        "video_id": video_id,
        "duration_seconds": duration,
        "transcript_source": tr["source"],
        "title": meta["title"],
        "author": meta["author"],
        "thumbnail": meta["thumbnail"],
        "summary": summary,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
