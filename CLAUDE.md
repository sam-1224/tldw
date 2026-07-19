# CLAUDE.md

Project context for Claude Code. Read this AND `HANDOFF_V2.md` fully before
changing anything. `HANDOFF_V2.md` is the authoritative staged roadmap with
success criteria and stage gates; this file holds the always-true context.

## What this is

**TL;DW** ("Too long; didn't watch") — an open-source YouTube summarizer
evolving into an AI video learning workspace. Paste a URL → TL;DR +
timestamped key moments → (roadmap) ask questions, build a knowledge base,
export everywhere.

Pipeline: `free transcript → optional Supadata fallback → chosen LLM → summary`.

## Stack

- **Backend:** FastAPI (`backend/main.py`), transcript logic in
  `backend/transcript.py`, provider-agnostic LLM in `backend/summarize.py`
  (plain `httpx`; Anthropic / OpenAI / Gemini / Groq).
- **Frontend:** currently a single static `frontend/index.html`. Stage 2 of
  `HANDOFF_V2.md` deliberately migrates it to **Vite + React + TypeScript +
  Tailwind + shadcn/ui** (with selective MagicUI/Aceternity components,
  Motion for micro-interactions, GSAP only on landing scroll). After Stage 2,
  FastAPI serves `frontend/dist`.
- **No-code variant:** `n8n/workflow.json`.

## How to run (pre-Stage-2)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000    # serves API + current frontend
```
Docker: `docker compose up --build`. Post-Stage-2 dev flow is defined in
HANDOFF_V2.md §5.5 and must be reflected in the README when it lands.

## Invariants — never break

1. **BYOK.** Browser-supplied keys override env fallbacks and are never
   logged, persisted server-side, or sent anywhere but the chosen provider.
2. **Free transcript path first.** `youtube-transcript-api` before Supadata;
   Supadata only when the user supplied a key.
3. **Backend dependency minimalism.** No per-provider LLM SDKs; `httpx` only.
   New backend deps need explicit justification.
4. **Brand system.** Marigold `#F2A30F` is the single accent; ink/paper
   palette (dark-first from Stage 2 — tokens in HANDOFF_V2.md §5.2); fonts
   Bricolage Grotesque / Inter / JetBrains Mono. The scrubber-with-highlight-
   ticks is the signature element — keep it central.
5. **Accessibility + motion safety.** WCAG AA, keyboard operable,
   `prefers-reduced-motion` collapses animations to ≤150ms fades.
6. **Stage gates.** Follow HANDOFF_V2.md order; present the Definition of
   Done with evidence and wait for approval before the next stage.

## Dependency constraints — these caused real breakage

- Python 3.11–3.14 supported. `requirements.txt` uses `>=` floors on purpose.
  **Never hard-pin `pydantic` below 2.12** (forces a Rust source build of
  pydantic-core that fails on 3.14). `uvicorn[standard]` is fine (uvloop
  0.22.1+ ships 3.14 wheels).
- **`youtube-transcript-api` must stay `>=1.2.3` (1.x API).** Instance-based:
  ```python
  ytt_api = YouTubeTranscriptApi()
  raw = ytt_api.fetch(video_id, languages=[...]).to_raw_data()
  ```
  `YouTubeTranscriptApi.get_transcript(...)` was **removed in v1.2.0** —
  never call it or pin below 1.0. Error classes import from the package root.

## Working style

- One branch per stage; small imperative commits; tag on stage completion.
- Every backend logic change ships with pytest coverage in the same commit;
  frontend features ship with Playwright coverage from Stage 2 on.
- Run it before you report it: server boot, test output, screenshots.
- When docs and reality disagree, fix the docs in the same PR.

## Current position

Stages live in `HANDOFF_V2.md`: 0 baseline → 1 correctness+tests → 2 frontend
platform/redesign → 3 top-5 features → 4 MV3 extension → 5 traffic-gated
bets. **Start at Stage 0 unless a tag says otherwise.**
