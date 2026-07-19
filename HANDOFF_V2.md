# TL;DW — Master Handoff & Staged Roadmap (v2)

> **2026-07-19 deviation (approved by Saumitra):** free-first shipped before
> Stage 0/1. The app now works keylessly for visitors via server env keys with
> a failover chain (gemini → groq → cerebras, `FREE_CHAIN` in
> `backend/main.py`), plus a multi-provider BYOK registry
> (`PROVIDERS` in `backend/summarize.py`: gemini/groq/cerebras/openai/
> anthropic/xai/moonshot/deepseek/openrouter/custom base_url for local LLMs)
> with model catalogs served via `GET /api/config` and a Free/BYOK switch in
> the settings drawer. Puter.js was evaluated and rejected (signup friction).
> Backend tests live in `backend/tests/`. Stage 1's remaining scope
> (full transcript in response, CI, transcript tests) still applies.

**Audience:** Claude Code. Read fully before writing any code.
**Owner:** Saumitra. He reviews and approves at every stage gate.
**Prime directive:** Never advance to the next stage until the current stage's
Definition of Done is fully checked. Working software at every stage.

---

## 0. Product thesis (why these stages, in this order)

TL;DW's edge is: transcript already in hand + provider-agnostic LLM + BYOK =
near-zero hosting cost. The risk is being "just another summarizer." The
differentiator is features that keep users *inside* the tool: interrogating
videos, building a personal knowledge base, and exporting knowledge.

Stage order = risk order: verify the base → make it correct → make it stunning
→ make it sticky (top 5 features) → remove friction (extension) → scale bets
(gated on traffic).

---

## 1. Global engineering rules (apply to every stage)

1. **BYOK is sacred.** Keys come from the browser and override env fallbacks.
   Never log, persist server-side, or transmit keys anywhere except the chosen
   provider's API. Grep for key names in any new logging code before commit.
2. **Free path first.** `youtube-transcript-api` (1.x API: instance
   `.fetch(video_id, languages=[...]).to_raw_data()` — `get_transcript` was
   REMOVED in 1.2.0) before Supadata. Supadata only fires when the user
   supplied a key.
3. **Backend dependency minimalism.** LLM calls stay plain `httpx`. No
   per-provider SDKs. Every new backend dep needs a one-line justification in
   the PR description.
4. **Python 3.11–3.14 compatibility.** `requirements.txt` uses `>=` floors on
   purpose. Never hard-pin `pydantic < 2.12` (breaks pydantic-core wheels on
   3.14). Never pin `youtube-transcript-api < 1.0`.
5. **Git discipline.** One branch per stage (`stage-1-correctness`, etc.).
   Small commits, imperative messages. Tag on stage completion
   (`v0.1-stage1`). Never force-push main.
6. **Test with every logic change.** Backend changes ship with pytest coverage
   in the same commit. Frontend features ship with at least a smoke test
   (Playwright) from Stage 2 onward.
7. **Pause at every stage gate.** Present the Definition of Done checklist with
   evidence (test output, screenshots, Lighthouse scores) and wait for
   approval before starting the next stage.
8. **When docs and reality disagree, update the docs in the same PR.**

---

## 2. Stage map

| Stage | Name | Outcome | Gate |
|---|---|---|---|
| 0 | Baseline verification | Current app provably works end-to-end | Checklist §3.4 |
| 1 | Correctness & test foundation | Full transcript returned; pytest suite; CI | Checklist §4.5 |
| 2 | Frontend platform + redesign | Vite/React/Tailwind app at full feature parity, new design system | Checklist §5.7 |
| 3 | The Top 5 (stickiness) | Q&A, modes, history+tags, search+jump, export | Checklist §6.8 |
| 4 | Browser extension (MV3) | One-click TL;DW on YouTube pages | Checklist §7.5 |
| 5 | Growth bets (HOLD) | Playlist, flashcards/quiz, citations, PWA, audio | Traffic-gated, §8 |

Estimated effort: Stage 0 ≈ one short session. Stages 1–4 ≈ 2–5 sessions each.

---

## 3. STAGE 0 — Baseline verification

**Goal:** prove the shipped scaffold runs before touching anything, so future
breakage is attributable.

### 3.1 Tasks
1. Create venv, install `backend/requirements.txt`, boot
   `uvicorn main:app --reload --port 8000`.
2. `curl http://localhost:8000/api/health` → `{"ok": true}`.
3. Load `/`, confirm the current UI renders (fonts, scrubber input, drawer).
4. With a real key (Groq or Gemini free tier), summarize one captioned video.
   Confirm: TL;DR renders, key moments have timestamps, timeline ticks appear,
   clicking a tick opens YouTube at the right second.
5. Negative paths: bad URL → friendly 400; no key → drawer opens with message;
   wrong key → provider 401 surfaced cleanly.
6. `docker compose up --build` boots and serves on :8000 (smoke only).

### 3.2 Known sharp edges (do not "fix" these blindly)
- Sandbox/datacenter IPs are often blocked by YouTube — free path can fail
  where a home IP succeeds. That's environmental, not a bug.
- The "Full transcript" panel currently re-lists key points. That is the known
  P0 defect, fixed in Stage 1 — don't patch it here.

### 3.3 Tests
None written in this stage; this stage IS the manual test.

### 3.4 Definition of Done
- [ ] All of §3.1 pass, with a screenshot of one successful summary.
- [ ] Any environmental failures documented in `NOTES.md` (not "fixed").
- [ ] Tag `v0.0-baseline`.

---

## 4. STAGE 1 — Correctness & test foundation

**Goal:** the API tells the whole truth (full transcript), and a safety net
exists so the big Stage 2 rewrite can't silently break the backend.

### 4.1 API change — return the real transcript
Extend the `/api/summarize` response:
```jsonc
{
  // ...existing fields...
  "segments": [ {"text": str, "start": float, "duration": float}, ... ]
}
```
Update the current frontend's "Full transcript" panel to render real segments
(reuse `.tline` + `watchUrl()`); each timestamp deep-links. Cap the DOM: if
segments > 1500, render in chunks on scroll (simple `IntersectionObserver`).

### 4.2 Refactor seam for reuse
Extract transcript-fetch + summarize orchestration in `main.py` into a
function usable by future endpoints (`/api/ask` in Stage 3 will need the same
transcript path). No behavior change.

### 4.3 Test suite (pytest + pytest-mock or respx for httpx)
Backend tests in `backend/tests/`:
- `test_transcript.py`: `extract_video_id` — watch URL, youtu.be, shorts,
  embed, bare ID, garbage, empty; oEmbed fallback shape; free→Supadata
  fallback ordering (mock both layers); Supadata ms→s conversion; error
  mapping (`no_captions` without key → friendly message).
- `test_summarize.py`: `_extract_json` — clean, fenced, preamble+JSON, invalid
  → `SummarizeError`; `build_timestamped_text` truncation flag at boundary;
  provider routing hits correct URL/headers per provider (httpx mocked);
  401/429/500 → correct `SummarizeError` messages.
- `test_api.py` (FastAPI `TestClient`): happy path returns all fields incl.
  `segments`; bad URL → 400; missing key → 400; transcript failure → 422;
  request key overrides env key (assert the mocked LLM call saw the request
  key — this is the BYOK guarantee test).

### 4.4 CI
GitHub Actions workflow: on push/PR → set up Python 3.12 and 3.14 matrix →
install → `pytest -q`. Badge in README.

### 4.5 Definition of Done
- [ ] `pytest -q` green locally; ≥ 90% line coverage on `transcript.py` and
      `summarize.py` (pragmatic, not dogmatic — cover every branch that maps
      an error to a user-facing message).
- [ ] CI green on 3.12 and 3.14.
- [ ] Manual: summarize a real video; "Full transcript" shows genuine
      transcript lines with working deep links.
- [ ] README test instructions updated. Tag `v0.1-stage1`.

---

## 5. STAGE 2 — Frontend platform + the redesign

**Goal:** rebuild the frontend as a Vite + React + Tailwind app with a
design-system-first, dark-first, genuinely striking UI — at full feature
parity with the current app before any new features.

> **This stage retires the old "single static file" rule.** New rule: the
> frontend is a Vite app in `frontend/`; FastAPI serves `frontend/dist` as
> static files in production; `npm run dev` proxies `/api` to :8000 in dev.

### 5.1 Stack (deliberate choices)
- **Vite + React 18 + TypeScript.** Types catch API-contract drift.
- **Tailwind CSS v4** + **shadcn/ui** as the component base (Button, Dialog,
  DropdownMenu, Tabs, Tooltip, Sheet for the settings drawer, Sonner for
  toasts, Skeleton for loading).
- **MagicUI / Aceternity — selectively.** Shortlist (steal patterns, keep
  bundle lean): MagicUI *Bento Grid*, *Shimmer/Shiny text* (hero accent),
  *Border Beam* (active summary card), *Animated List* (key moments entrance),
  *Marquee* (landing social proof later). Aceternity *Spotlight* (hero),
  *Glowing card* treatment for the TL;DR block. Rule: copy the component in
  (both libraries are copy-paste model) — do NOT import whole kits.
- **Motion (motion.dev)** for UI micro-interactions (layout animations,
  presence, springs). **GSAP + ScrollTrigger** ONLY on the landing/marketing
  sections (scroll choreography); never inside the app's working views.
- **Lottie** (lottie-web, lazy-loaded) for exactly two moments: an empty-state
  animation and a "summary complete" micro-celebration. Nowhere else.
- No Redux; React Query for server state, Zustand (tiny) for local app state.

### 5.2 Design system — "Highlight OS" (evolution of the brand)
Grounded in what's actually holding up in 2026 production: dark-first, bento
structure, restrained glass, one kinetic moment, colored diffused glows.

**Color (dark-first, light theme secondary):**
```
--bg:        #0B0B10   (near-black, blue-leaning ink)
--bg-raise:  #14141B   (cards)
--bg-glass:  rgba(20,20,27,.6) + backdrop-blur (nav & modals ONLY)
--ink:       #F5F2EA   (warm paper as TEXT — brand inversion)
--ink-dim:   #9A97A3
--marigold:  #F2A30F   (the ONE accent; hover #FFB52E)
--marigold-glow: 0 0 40px rgba(242,163,15,.25)  (diffused colored shadow)
--positive:  #3ECF8E   --danger: #FF5C5C
--hairline:  rgba(245,242,234,.08)
Light theme = current paper palette, toggled, prefers-color-scheme respected.
```
**Type:** Bricolage Grotesque (display; use its variable optical axis large in
the hero), Inter (UI), JetBrains Mono (timestamps/keys/data). Fluid scale via
`clamp()`; hero ~ clamp(44px, 9vw, 96px).

**Signature elements (the memorable 20%):**
1. **The Scrubber** stays the brand centerpiece, upgraded: input row styled as
   a player bar; on submit it becomes a real progress bar; on result the
   marigold **highlight ticks** drop onto it with a spring stagger (Motion),
   glowing with `--marigold-glow`; hover shows a mono tooltip of the moment.
2. **Kinetic hero — one moment only:** headline "Watch less. Know more."
   where "Know more." reveals with a highlighter-swipe (clip-path animation),
   and a slow shimmering gradient pass over "Know" (MagicUI shiny-text). No
   other kinetic type anywhere.
3. **Bento results layout:** CSS grid of cards — TL;DR (2×2, ink card with
   marigold glow + Border Beam while streaming), Key Moments (tall), Worth
   It?/meta (small), Topics (small), Transcript (full-width collapsible),
   Q&A dock (Stage 3 slot, full-width). Cards enter with 60ms stagger,
   opacity+8px rise, spring.
4. **Glass, restrained:** sticky top nav and the settings Sheet only.
5. **Micro-delights:** buttons scale 0.98 on press; timestamps pulse once on
   copy; toast confirmations; skeleton shimmer during load; loading state
   cycles the playful mono status lines from v1.

**Accessibility & motion safety:** WCAG AA contrast in both themes; visible
focus rings (marigold, 2px offset); full keyboard operability;
`prefers-reduced-motion` collapses ALL animation to fades ≤150ms; aria-live
on the loading status.

**Performance budgets (hard gates):** Lighthouse (mobile, Fast 3G throttle):
Performance ≥ 85, A11y ≥ 95, Best Practices ≥ 95. JS ≤ 250KB gzip initial
(GSAP + Lottie lazy-loaded only on landing routes). CLS < 0.1, LCP < 2.5s.
`npm run build` prints bundle report; paste it at the gate.

### 5.3 Information architecture
Single-page app, two zones: **Landing zone** (hero + scrubber + how-it-works
bento + FAQ; GSAP scroll reveals live here) and **App zone** (results bento +
history sidebar placeholder). Route `/` covers both (landing collapses once a
summary exists). Settings = Sheet (right), same fields as v1 + theme toggle.

### 5.4 Parity checklist (must equal v1 before the gate)
Submit URL (Enter + button) → loading states → error states (bad URL / no key
/ wrong key / no captions) → results (TL;DR, key moments with deep links,
timeline ticks, topics, full real transcript with lazy render) → settings
(provider, LLM key, Supadata key, model override, persistence in
localStorage) → mobile layout → keyboard: Esc closes sheet, Enter submits.

### 5.5 Serving & dev ergonomics
- `frontend/`: `npm create vite@latest` (react-ts). `npm run dev` on :5173
  proxying `/api`.
- FastAPI mounts `frontend/dist` (StaticFiles, html=True) when it exists;
  keeps working with zero frontend build for API-only dev.
- Dockerfile becomes two-stage: node build → python runtime copying `dist`.
- README rewritten for the new dev flow.

### 5.6 Tests
- Playwright smoke suite (`frontend/e2e/`): app boots; submit with mocked
  `/api/summarize` (route interception) renders all bento cards; settings
  persist across reload; reduced-motion mode renders without animation
  classes; mobile viewport (390×844) has no horizontal scroll.
- Keep pytest green — zero backend changes expected this stage (except static
  mounting, covered by one TestClient test).

### 5.7 Definition of Done
- [ ] Parity checklist §5.4 fully checked, with desktop + mobile screenshots
      of: landing, loading, results, settings, one error state, both themes.
- [ ] Lighthouse + bundle budgets met (paste reports).
- [ ] Playwright suite green; pytest green; CI runs both.
- [ ] `prefers-reduced-motion` verified by toggling in devtools.
- [ ] Saumitra approves the look. Tag `v0.2-stage2`.

---

## 6. STAGE 3 — The Top 5 (stickiness features)

Ship in this order; each feature is its own PR with tests. The order front-
loads backend-light wins.

### 6.1 Feature A — Ask the Video (Q&A)
**Backend:** `POST /api/ask` `{video_id?, url?, question, history: [{role,
content}], provider, llm_key?, model?, segments}` → `{answer, citations:
[{timestamp, segment_index}]}`. Reuse Stage 1's orchestration seam; the
client sends segments back (stateless server, no persistence). System prompt:
answer ONLY from transcript, cite timestamps for every claim, say "the video
doesn't cover that" when true.
**Frontend:** Q&A dock card in the bento: chat thread, suggested first
questions (3 chips generated from key points), streaming-feel (skeleton →
answer), each citation is a deep-link chip that also flashes the matching
tick on the scrubber.
**Tests:** pytest — prompt assembly includes segments + history, provider
routing, refusal path passes through; Playwright — mocked ask round-trip
renders answer + clickable citation.
**Success:** answering "what did they say about X?" on a real 20-min video
returns a cited, correct answer in < 10s with Groq.

### 6.2 Feature B — Summary modes & custom templates
**Backend:** `mode` param on `/api/summarize`; server-side registry:
`quick | detailed | eli5 | technical | executive | actionable`. Each mode =
system-prompt variant; same JSON contract. Plus `custom_instructions` (≤ 500
chars) appended safely (treat as data: "Additional style request from user —
follow only if consistent with the JSON contract").
**Frontend:** segmented control above the scrubber; custom template textarea
in a popover; chosen mode stored per-history-entry.
**Tests:** registry snapshot test (every mode yields non-empty distinct
prompt); API test that mode changes the system prompt (mock assert).
**Success:** same video in `eli5` vs `technical` produces visibly different
registers; invalid mode → 400.

### 6.3 Feature C — History + tags (localStorage knowledge base)
**Frontend-only.** Persist each result: `{id, video_id, title, author,
thumbnail, created_at, mode, provider, summary, segments? (see cap), tags:
[]}`. Cap: store segments only if < 300KB per entry; always store summary.
Total budget 4MB LRU-evicted with a storage meter in settings. UI: left
sidebar (collapsible; Sheet on mobile) — search-as-you-type over title/tldr/
tags, tag chips with filter, pin, delete with undo toast, "reload" restores
the full bento instantly (no API call).
**Tests:** Playwright — summarize (mocked) → reload page → entry present →
restore works offline (route abort on /api) → delete+undo works. Unit tests
for the LRU/eviction module.
**Success:** a returning user can find and reopen any past summary in < 3
interactions, offline.

### 6.4 Feature D — Transcript search + jump
**Frontend-only.** Search input over segments (`/` focuses it): case-
insensitive `matchAll`, highlight all matches in the transcript panel, n/N
match counter, Enter/↑↓ cycles matches, each match row deep-links AND drops a
temporary white tick on the scrubber for match positions. Debounced 150ms;
handles 5,000 segments without jank (virtualize the transcript list —
`@tanstack/react-virtual`).
**Tests:** unit — match indexing incl. multi-match per segment, unicode;
Playwright — search "the" in a 1,000-segment mocked transcript stays > 30fps
interaction (no assertion on fps, assert render count stays bounded via
virtualization) and jumping cycles matches.
**Success:** finding a phrase in an hour-long video takes < 5 seconds.

### 6.5 Feature E — Export ecosystem
**Frontend-first.** Export menu on the results header: **Markdown** (title,
link, TL;DR, key moments as `[m:ss](youtube.com/watch?v=..&t=..)` bullets,
topics), **Plain text**, **JSON** (full result object), **Notion-flavored
Markdown** (toggle headings), **copy-for-Slack** (mrkdwn). Copy-to-clipboard
+ file download for each. Include "summarized with TL;DW" footer (removable).
**Tests:** unit — each formatter snapshot-tested against a fixture result;
timestamps convert to correct `&t=` seconds; Playwright — copy puts correct
content on clipboard (Playwright clipboard permissions).
**Success:** pasting the Markdown export into Notion/Obsidian renders
correctly with working deep links.

### 6.6 Polish bundle (single PR, after A–E)
Reading-time + "time saved" badge (`duration` vs summary word count / 200wpm);
keyboard shortcuts (⌘/Ctrl+Enter submit, `/` search, j/k key-moment nav, Esc
close) with a `?` shortcuts overlay; "Worth watching?" 1–10 + one-liner added
to the summary JSON contract (backend prompt tweak + one card slot).

### 6.7 Cross-cutting tests for the stage
Full-journey Playwright: paste URL → summarize (mocked) → ask a question →
switch mode → re-summarize → tag it → search transcript → export Markdown →
reload → restore from history. This is the release test from now on.

### 6.8 Definition of Done
- [ ] A–E each merged with their tests; polish bundle merged.
- [ ] Full-journey test green in CI.
- [ ] Budgets from §5.2 still met (re-run Lighthouse; paste report).
- [ ] One real-key end-to-end video demo recorded (screen capture) for A–E.
- [ ] README feature docs updated. Tag `v0.3-stage3`.

---

## 7. STAGE 4 — Browser extension (Manifest V3)

**Goal:** kill the copy-paste friction. One click on any YouTube watch page
opens TL;DW with that video summarized.

### 7.1 Scope decision (keep it thin — v1 is a launcher, not a port)
The extension does NOT reimplement the app. It: (a) injects a small marigold
**TL;DW button** next to the like/share row on `youtube.com/watch*`, and (b)
on click opens `https://<app-host>/?v=<video_id>&autorun=1` in a new tab
(the web app gains support for those params: prefill + auto-submit). Also a
toolbar popup with a URL field + "Summarize" + last 5 history titles (read
from `chrome.storage` mirror written by the web app via a tiny postMessage
bridge — optional, cut if fiddly).
Rationale: keys stay in ONE place (the web app), review surface stays tiny,
and Stage 3 history keeps working. A full in-extension UI is a Stage 5 bet.

### 7.2 Build
`extension/` workspace: MV3 manifest (minimal permissions: `activeTab`,
`storage`; content script matched to `*://*.youtube.com/watch*`), Vite build
(reuse design tokens; the button uses brand marigold + tooltip). Handle
YouTube's SPA navigation (yt-navigate-finish event) so the button survives
in-app navigation. Dark/light aware.

### 7.3 App-side support
`/` reads `?v=` + `autorun=1` → prefill + submit (only if a key exists;
otherwise open settings with a hint). Covered by a Playwright test.

### 7.4 Tests & review prep
Manual matrix: Chrome + Edge + Brave; navigation SPA case; button idempotency
(no duplicates on re-render). Store checklist: icons (16/32/48/128), 1280×800
screenshots, privacy note ("no data collected; opens tl-dw app"), single-
purpose description. Load-unpacked instructions in `extension/README.md`.

### 7.5 Definition of Done
- [ ] Button appears reliably across 10 consecutive SPA navigations.
- [ ] Click → app opens → auto-summarizes (with key present).
- [ ] Zero console errors on YouTube; no layout breakage of YouTube UI.
- [ ] Store-ready zip + assets produced (submission itself is Saumitra's).
- [ ] Tag `v0.4-stage4`.

---

## 8. STAGE 5 — Growth bets (HOLD until traffic justifies)

Do not build these yet. Revisit when: ≥ 200 weekly active summarizers OR a
concrete user request pattern. Pre-scoped so they're ready to lift:

1. **Playlist / multi-video synthesis** — needs chunked map-reduce (also
   fixes long-video truncation; if long-video complaints arrive early, lift
   just the map-reduce piece into a point release).
2. **Flashcards (Anki CSV/TSV) + quiz mode** — prompt templates + export;
   natural after modes infra exists.
3. **Citation footnotes** in summaries — extend JSON contract with
   `segment_index` per point.
4. **PWA** (manifest + service worker; offline history already works).
5. **Audio/podcast upload** via Groq Whisper — one new endpoint; respect
   upload size limits.
6. **Anti-goals (do not build without a written plan):** accounts/sync, team
   workspaces, server-side history, fact-check mode (trust risk: wrong flags
   on a trust feature destroy trust), sentiment arcs, speaker diarization.

---

## 9. Kickoff prompt (paste this to Claude Code, in the repo root)

```
Read HANDOFF_V2.md and CLAUDE.md fully. Then skim backend/ and frontend/.

We execute HANDOFF_V2.md stage by stage. Rules: follow §1 global engineering
rules; never advance past a stage gate without presenting the Definition of
Done checklist with evidence and getting my approval; one branch per stage.

Start with STAGE 0 (baseline verification). Present your verification plan
first (which commands, which video URL, which provider you need a key for),
then execute and report results against §3.4.
```

---

## 10. Evidence format at every gate

Post: checklist with ✅/❌ · test summary (`pytest`/Playwright output tail) ·
screenshots (desktop + mobile where UI changed) · Lighthouse + bundle report
(Stages 2+) · what was deferred and why · proposed plan for next stage.
