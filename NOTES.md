# Environmental notes

- **YouTube IP rate-limit ("blocking requests from your IP")** — confirmed
  IP-wide 2026-07-20: even a known-good video fails while oEmbed still works.
  Environmental, not a bug; datacenter/cloud IPs and repeated calls trigger it,
  home IPs usually don't. Bypasses, in order of effort:
  1. Wait a few minutes (transient).
  2. Set a Supadata key in settings (different backend, already wired).
  3. **Residential proxy** for the free path (best for hosted/public instances)
     — `WEBSHARE_PROXY_USERNAME`/`_PASSWORD` (Webshare rotating) or
     `YT_PROXY_HTTP`/`YT_PROXY_HTTPS` (any proxy). See `.env.example`.
     Wired via `transcript._proxy_config()`; costs nothing when unset.

- **Non-English videos verified 2026-07-19**: Hindi-only video
  (P12Flimn_jQ) transcribes via any-language fallback (`language: "hi"`),
  summary translated to English, badge shows "captions · HI → EN".
- **LLMs occasionally emit broken JSON** even with JSON mode on (seen once
  with Gemini on a Hindi transcript) — `summarize()` retries once, parser
  raises clean SummarizeError instead of crashing with a 500.

- **Docker not installed** on this machine (Windows 11, 2026-07-19) — Docker
  smoke test skipped, not a code defect. Two-stage Dockerfile untouched.
- **Live free-mode verified 2026-07-19**: keyless summary of a real video via
  Gemini free tier (`gemini-flash-latest`), timeline ticks + deep links OK,
  wrong-key 502 surfaced cleanly, bad URL 400.
- **Gemini model ids rot for new keys**: `gemini-2.5-flash` returns 404
  "no longer available to new users" on fresh API keys — use the
  `gemini-flash-latest` / `-pro-latest` aliases, they track current models.
- **Machine-global env vars can shadow `.env`**: this machine had a stale
  `GEMINI_API_KEY` in Windows user env. `backend/main.py` now loads
  `backend/.env` with `override=True` so the project file wins. If that old
  global key is unused, consider deleting it (`Remove-Item Env:` only clears
  the session; remove via Windows env settings) and rotating if it's live.
- **Known P0 (pre-existing, do not patch ad-hoc)**: the "Full transcript"
  panel re-lists key points instead of real segments. Owned by HANDOFF_V2
  Stage 1 (return `segments` from `/api/summarize`).
- Datacenter/sandbox IPs are often blocked by YouTube — free transcript path
  can fail where a home IP succeeds. Environmental, not a bug.
