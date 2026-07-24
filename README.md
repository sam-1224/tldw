# TL;DW — Too long; didn't watch

Paste a YouTube link, get the gist with jump-to-the-moment timestamps. Open
source, bring-your-own-key, and cheap to run because it tries the **free**
transcript route first.

![status](https://img.shields.io/badge/license-MIT-black) ![status](https://img.shields.io/badge/BYOK-yes-f2a30f)

---

## Why it's cheap

Most "YouTube summarizer" tools route everything through a paid transcript API.
TL;DW tries the free [`youtube-transcript-api`](https://pypi.org/project/youtube-transcript-api/)
library first, which costs nothing and covers the majority of videos. It only
falls back to **Supadata** (Whisper AI transcription) when a video has no
captions — and only if you provide a Supadata key.

For the LLM step it's **provider-agnostic**: Gemini, Groq, Cerebras, OpenAI,
Anthropic Claude, xAI Grok, Moonshot Kimi, DeepSeek, OpenRouter, or any
OpenAI-compatible server (Ollama, LM Studio, vLLM) via the custom provider.

```
paste URL ──► youtube-transcript-api (free)
                 └─ no captions? ──► Supadata AI fallback (optional key)
              └─► free-tier model (no key) or your chosen LLM
              └─► TL;DR + timestamped key moments
```

## Who provides the key?

**Visitors don't need one.** Free mode: the instance owner sets one free-tier
key in `.env` (Gemini's free tier is generous — no card, ~1,500 req/day) and
every visitor summarizes keylessly. Add `GROQ_API_KEY` / `CEREBRAS_API_KEY`
too and the server fails over automatically when a free tier rate-limits.

**BYOK for premium models.** Each user can enter their own key in the in-app
settings drawer — stored in that person's browser (`localStorage`), never on a
server, and a browser key always overrides the server's. So you can publish a
public instance without holding anyone's secrets, and users who want
Claude/GPT/Grok quality pay only their own provider.

---

## Run it

### Option 1 — Docker (one command)

```bash
cp .env.example .env        # optional: add a default key
docker compose up --build
```

Open http://localhost:8000, click the gear, paste an API key, summarize.

### Option 2 — Local dev

```bash
# backend (serves API + built frontend when frontend/dist exists)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# frontend (Vite + React + TS; proxies /api to :8000)
cd frontend
npm install
npm run dev          # http://localhost:5173 with hot reload
npm run build        # emits frontend/dist for FastAPI to serve on :8000
```

Zero-frontend-build fallback: without `frontend/dist`, FastAPI serves the
pre-Stage-2 static app from `frontend/legacy/index.html`.

---

## Project layout

```
tldw/
├── backend/
│   ├── main.py          FastAPI app + /api/summarize, serves the frontend
│   ├── transcript.py    free library first, Supadata fallback, oEmbed metadata
│   ├── summarize.py     one provider-agnostic LLM call (httpx, no heavy SDKs)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── index.html       single-file UI, zero build step
├── n8n/
│   └── workflow.json    no-code version (import into n8n)
├── docker-compose.yml
└── .env.example
```

## Configuration

Everything is optional — the app works with browser-side keys alone.

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` / `GROQ_API_KEY` / `CEREBRAS_API_KEY` | Free-mode chain — keyless visitor summaries with rate-limit failover |
| `DEFAULT_PROVIDER` | First provider keyless requests try (default `gemini`) |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `XAI_API_KEY` / `MOONSHOT_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` | Env fallback for those providers |
| `SUPADATA_API_KEY` | Default fallback transcript key |

Per-provider model catalogs (with defaults) live in `backend/summarize.py`
(`PROVIDERS`) and are served to the UI via `GET /api/config`; the settings
drawer offers dropdowns plus a free-text model override.

### Tests

```bash
cd backend
pip install pytest respx
python -m pytest tests -q
```

---

## The no-code version (n8n)

`n8n/workflow.json` is the same pipeline as a no-code flow:

1. Start n8n — `npx n8n` or `docker run -it --rm -p 5678:5678 n8nio/n8n`.
2. **Workflows → Import from File →** `n8n/workflow.json`.
3. Replace `REPLACE_WITH_SUPADATA_KEY` and `REPLACE_WITH_LLM_KEY` (or wire up
   proper n8n credentials).
4. Activate, then `POST {"url": "https://youtu.be/…"}` to the webhook URL.

Swap the OpenAI node for any provider's chat endpoint, or add a Notion / Slack
node after it to file the summary somewhere.

> Note: Supadata's free tier is rate-limited (1 req/sec, 100 credits/month, no
> rollover), so a shared key drains fast. BYOK per user is the way to scale.

---

## Notes & limits

- Private videos can't be transcribed by any method.
- **YouTube may rate-limit a server's IP** ("blocking requests from your IP")
  on the free transcript path — common on cloud/datacenter hosts, rare on a
  home IP. Fixes: wait a few minutes, add a Supadata key, or (best for a public
  instance) set a residential proxy via `WEBSHARE_PROXY_USERNAME`/`_PASSWORD`
  or `YT_PROXY_HTTP`/`YT_PROXY_HTTPS` — see `.env.example`.
- Very long transcripts are trimmed before summarizing to keep token cost down
  (the UI flags when this happens).
- Respect each provider's rate limits if you batch.
- This is a starting point — PRs welcome for caching, batch mode, more
  providers, and a download-as-markdown button.

## License

MIT. See [`LICENSE`](./LICENSE).
