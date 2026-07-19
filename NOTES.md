# Environmental notes

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
