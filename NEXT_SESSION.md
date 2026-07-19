# TL;DW — Next Session Plan

Fresh-session context handoff. Read `CLAUDE.md` + `HANDOFF_V2.md` first (the
always-true rules and staged roadmap), then this for where we actually are.

---

## Where we are (as of 2026-07-19)

Repo: `D:\PROJECTS\tldw\tldw`. GitHub: `sam-1224/tldw` (branch `main`).
Python 3.13 venv in `backend/.venv`. Node 22. **Docker not installed** (fine).

### Shipped and verified live
- **Free-first, zero-friction summaries.** Keyless visitors summarize via
  server env keys. Chain in `backend/main.py` `FREE_CHAIN = [gemini, groq,
  cerebras]`; fails over on 429 **and** 413. `DEFAULT_PROVIDER` env picks the
  first (default gemini, `gemini-flash-latest`).
- **10-provider BYOK registry** (`PROVIDERS` in `backend/summarize.py`):
  gemini, groq, cerebras, openai, anthropic, xai, moonshot, deepseek,
  openrouter, custom (Ollama/LM Studio via base_url, key-optional). Model
  catalogs served by `GET /api/config`. Free/BYOK switch + model dropdowns
  in settings. BYOK key overrides env, never logged/persisted.
- **Any-language transcripts** — fetches any caption track (Hindi/Filipino
  verified), LLM translates to the chosen **summary language** (`summary_lang`
  param, `SUMMARY_LANGUAGES` catalog, dropdown, 15 langs).
- **Rich summary contract**: tldr, breakdown[], key_points[] w/ detail,
  takeaways[], worth_watching{score,reason}, topics[]. Real transcript panel
  with deep links, chunked render (200/scroll) — 10h video = 20ms.
- **Per-model free-tier fitting**: completion capped at 3000 tokens; Groq gets
  tighter transcript budget; on 413, transcript halves and retries. All Groq
  models work now (were failing with 413).
- **Dark mode toggle** (localStorage + prefers-color-scheme).
- **Stage 2 scaffold**: `frontend/` is Vite + React 18 + TS + Tailwind v4,
  full parity with the old static app. FastAPI serves `frontend/dist`; old app
  kept at `frontend/legacy/index.html` as zero-build fallback. Two-stage
  Dockerfile. Bundle 52KB gzip (budget 250KB).
- **Tests**: 48 pytest passing (`backend/tests/`). CI workflow (3.12/3.14)
  in `.github/workflows/ci.yml`.

Tags: `v0.1-free-first`, `v0.2-stage1`.

### Known limits (documented in NOTES.md, not bugs)
- YouTube rate-limits datacenter/repeated IPs on the transcript endpoint —
  transient, clean error surfaced, Supadata key bypasses.
- Gemini free tier has a daily quota; heavy testing exhausts it (resets daily).
  Auto mode fails over to Groq.
- Groq free tier caps tokens/min → long videos summarized from a **truncated**
  transcript (UI flags it). Gemini reads whole transcript.
- Gemini fixed model ids (e.g. `gemini-2.5-flash`) get withdrawn for new API
  keys — we use `-latest` aliases.

---

## How to start the next session

```bash
# backend
cd D:\PROJECTS\tldw\tldw\backend
.venv\Scripts\activate
uvicorn main:app --reload --port 8000     # loads backend/.env (has GEMINI + GROQ keys)

# frontend dev (hot reload, proxies /api to :8000)
cd D:\PROJECTS\tldw\tldw\frontend
npm run dev                               # http://localhost:5173

# after frontend changes, rebuild so FastAPI serves them on :8000
npm run build

# tests
cd backend && python -m pytest tests -q
```

`backend/.env` holds working GEMINI_API_KEY + GROQ_API_KEY (gitignored).

---

## Next up: finish Stage 2 (the redesign)

Scaffold is done; the actual **"Highlight OS" redesign** from HANDOFF_V2 §5.2
is NOT. This is the main Stage 2 work. In priority order:

1. **Bento results layout** (§5.2 signature #3) — CSS grid of cards: TL;DR
   (large, marigold glow), Key Moments (tall), Worth-It/meta (small), Topics
   (small), Transcript (full-width collapsible). Cards enter with stagger.
2. **The Scrubber upgrade** (§5.2 signature #1) — input row as a player bar;
   on submit becomes progress bar; marigold highlight ticks drop with spring
   stagger. This is THE brand centerpiece — keep it central.
3. **Kinetic hero** (§5.2 signature #2) — "Know more." highlighter-swipe
   reveal, one kinetic moment only.
4. **shadcn/ui components** — Dialog/Sheet (settings), Tabs (Free/BYOK),
   Tooltip, Sonner (toasts), Skeleton (loading). Copy-in, don't import kits.
5. **Motion (motion.dev)** for micro-interactions; **GSAP + ScrollTrigger**
   ONLY on landing scroll (never in app views); **Lottie** lazy for exactly
   two moments (empty state + summary-complete).
6. **Landing zone vs app zone** (§5.3) — hero+scrubber+how-it-works bento+FAQ
   collapses once a summary exists.

### Stage 2 Definition of Done (§5.7) — must clear before tagging v0.2-stage2
- [ ] Parity checklist §5.4 fully green, desktop + mobile screenshots of:
      landing, loading, results, settings, one error, both themes.
- [ ] Lighthouse (mobile, Fast 3G): Perf ≥85, A11y ≥95, BP ≥95. JS ≤250KB
      gzip initial (GSAP/Lottie lazy on landing only). CLS <0.1, LCP <2.5s.
      Paste `npm run build` bundle report at the gate.
- [ ] **Playwright smoke suite** (`frontend/e2e/`) — NOT written yet: app
      boots; mocked `/api/summarize` renders all bento cards; settings persist
      across reload; reduced-motion renders without animation classes; mobile
      390×844 no horizontal scroll.
- [ ] `prefers-reduced-motion` collapses all animation to ≤150ms fades.
- [ ] pytest still green; CI runs both suites.
- [ ] Saumitra approves the look. Tag `v0.2-stage2`.

---

## After Stage 2: Stage 3 (Top 5 stickiness features)

Backend seam ready: `build_llm_attempts()` in `main.py` is the shared
provider/failover path `/api/ask` will reuse. Order (HANDOFF_V2 §6):
A. Ask the Video (Q&A) — `POST /api/ask`, cited answers.
B. Summary modes (quick/detailed/eli5/technical/executive) — prompt variants
   over the existing rich contract (already parameterized via `_system_prompt`).
C. History + tags (localStorage KB).
D. Transcript search + jump (`@tanstack/react-virtual`).
E. Export (Markdown/JSON/Notion/Slack).

---

## Open decisions for Saumitra
- Deploy target? (affects whether/when Docker matters — Fly/Render/Railway/VPS)
- Set a public instance's own free-tier keys, or ship BYOK-only publicly?
- React Query + Zustand now, or defer until Stage 3 state grows? (currently
  plain useState — fine at this size)
