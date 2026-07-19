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

For the LLM step it's **provider-agnostic**: Anthropic, OpenAI, Gemini, or
Groq. For a genuinely free stack, use **Gemini Flash** or **Groq** — both have
generous free tiers.

```
paste URL ──► youtube-transcript-api (free)
                 └─ no captions? ──► Supadata AI fallback (optional key)
              └─► your chosen LLM ──► TL;DR + timestamped key moments
```

## Who provides the key?

This is the usual open-source question. TL;DW is **BYOK**: each user enters
their own keys in the in-app settings drawer, and they're stored in that
person's browser (`localStorage`) — never on a server. You can also drop keys
in `.env` if you want your instance to provide a default for everyone. A key
sent from the browser always overrides the server's.

That means you can publish a public instance **without paying for anyone
else's usage** and without holding their secrets.

---

## Run it

### Option 1 — Docker (one command)

```bash
cp .env.example .env        # optional: add a default key
docker compose up --build
```

Open http://localhost:8000, click the gear, paste an API key, summarize.

### Option 2 — Local Python

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open http://localhost:8000.

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
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` | Default LLM key for your instance |
| `SUPADATA_API_KEY` | Default fallback transcript key |

Default models (override per-request in the settings drawer):
`claude-3-5-haiku-latest`, `gpt-4o-mini`, `gemini-1.5-flash`,
`llama-3.3-70b-versatile`.

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
- Very long transcripts are trimmed before summarizing to keep token cost down
  (the UI flags when this happens).
- Respect each provider's rate limits if you batch.
- This is a starting point — PRs welcome for caching, batch mode, more
  providers, and a download-as-markdown button.

## License

MIT. See [`LICENSE`](./LICENSE).
