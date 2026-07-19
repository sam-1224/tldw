> **NOTE:** This file is superseded by `HANDOFF_V2.md`, the staged master plan. Steps 0–4 below (install & launch Claude Code) remain valid; for what to build, follow HANDOFF_V2.md.

# Handing TL;DW to Claude Code

A step-by-step to get this project running and continue it in Claude Code.
Should take about 10 minutes the first time.

---

## Step 0 — What you need

- A computer running macOS, Linux, or Windows (Windows works best via WSL).
- **Python 3.11+** (3.11, 3.12, 3.13, or 3.14 all work).
- A **paid Anthropic plan** (Claude Pro / Max / Team / Enterprise) **or** an
  Anthropic Console account with API credits. The free Claude.ai plan does not
  include Claude Code.
- An API key for at least one summary provider (Gemini or Groq are free tiers).

---

## Step 1 — Get the project onto your machine

1. Unzip `tldw.zip` somewhere sensible, e.g. `~/projects/tldw`.
2. Open a terminal in that folder:
   ```bash
   cd ~/projects/tldw
   ```
3. (Recommended) put it under version control so Claude Code's changes are easy
   to review and undo:
   ```bash
   git init && git add -A && git commit -m "Initial TL;DW scaffold"
   ```

---

## Step 2 — Verify it runs before involving Claude Code

Confirm the baseline works first, so any later breakage is clearly Claude Code's
change and not setup.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000, click the gear (top right), paste a Gemini or Groq
API key, pick that provider, and summarize any YouTube link with captions.

If `pip install` fails with a `pydantic-core` / `maturin` build error, your
Python is very new and a transitive package lags — easiest fix is to point the
venv at Python 3.13 instead (`python3.13 -m venv .venv`) or use Docker
(`docker compose up --build`). The pinned requirements are already set up to
avoid this on 3.14, so it should just work.

When it's working, stop the server (Ctrl-C). You can leave the venv as is.

---

## Step 3 — Install Claude Code

Two options. The **native installer is recommended** — no Node.js needed, and it
auto-updates.

**macOS / Linux (native):**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows (native, in PowerShell):**
```powershell
irm https://claude.ai/install.ps1 | iex
```

**Or via npm** (needs Node.js 18+; use this if npm is already your workflow):
```bash
npm install -g @anthropic-ai/claude-code
```
> Never use `sudo` with the npm install — if you hit a permission error, set a
> user-owned global dir (`npm config set prefix ~/.npm-global`) or use nvm.

Open a **new** terminal so your PATH updates, then verify:
```bash
claude --version       # prints a version number
claude doctor          # optional: checks install + auth
```

There's also a **Desktop app** (macOS/Windows) if you prefer a GUI over the
terminal — same tool, no command line required.

---

## Step 4 — Launch Claude Code in the project

```bash
cd ~/projects/tldw      # the project ROOT, not backend/
claude
```

On first launch it opens your browser for a one-time sign-in (OAuth), or you can
authenticate with an API key for headless setups.

Because the repo contains a **`CLAUDE.md`** at its root, Claude Code reads your
project's stack, invariants, and task backlog automatically — you don't have to
re-explain any of it each session.

---

## Step 5 — Kick it off

Paste this as your first message. (It mostly just points Claude Code at
`CLAUDE.md` and tells it where to start — the detail already lives in that file.)

```
Read CLAUDE.md fully, then skim backend/main.py, backend/transcript.py,
backend/summarize.py, and frontend/index.html before changing anything.

Pay special attention to the "Invariants" and "Dependency constraints" sections
of CLAUDE.md — in particular: keep youtube-transcript-api on the 1.x API
(.fetch().to_raw_data(), not the removed get_transcript), don't hard-pin
pydantic below 2.12, don't add per-provider LLM SDKs, and keep the frontend a
single static file.

Then start on P0 task 1 (return the real transcript from /api/summarize and
render it in the "Full transcript" panel). Confirm your plan before you edit,
make the change, run the server to verify, then show me the diff and pause.
```

That's it. From here you work conversationally — review each diff, approve or
redirect, and let it move down the backlog in `CLAUDE.md`.

---

## Handy Claude Code commands once you're in

- Describe a change in plain English; it proposes edits you approve or reject.
- `/bug` — report a Claude Code issue.
- Ask it to "run the tests" or "start the server and check localhost:8000".
- Edit `CLAUDE.md` any time to add conventions or reprioritize the backlog; it
  picks up the changes next session.

## If something breaks

- **Free transcript suddenly fails for many videos:** usually YouTube changed
  its internal format or your IP is rate-limited — `pip install --upgrade
  youtube-transcript-api` (staying on 1.x) and try from a home IP.
- **A summary errors with a 401:** the provider key is wrong for the selected
  provider in the settings drawer.
- **Install/build errors on a brand-new Python:** see the note in Step 2.
