# Environmental notes

- **Docker not installed** on this machine (Windows 11, 2026-07-19) — Docker
  smoke test skipped, not a code defect. Two-stage Dockerfile untouched.
- **Real free-tier key pending**: server verified with a placeholder
  `GEMINI_API_KEY`; Saumitra to create a free key at aistudio.google.com and
  put it in `backend/.env` (never committed) for the live end-to-end check.
- **Known P0 (pre-existing, do not patch ad-hoc)**: the "Full transcript"
  panel re-lists key points instead of real segments. Owned by HANDOFF_V2
  Stage 1 (return `segments` from `/api/summarize`).
- Datacenter/sandbox IPs are often blocked by YouTube — free transcript path
  can fail where a home IP succeeds. Environmental, not a bug.
