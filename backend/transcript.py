"""
Transcript fetching.

Strategy (cheapest first):
  1. youtube-transcript-api  -> free, self-hosted, no key. Works when captions exist.
  2. Supadata               -> optional fallback. Uses Whisper AI to transcribe
                               videos that have no captions. Needs a Supadata key.

Both paths are normalised to the same shape:
    segments = [{"text": str, "start": float_seconds, "duration": float_seconds}, ...]
"""

from __future__ import annotations

import os
import re
import httpx

# youtube-transcript-api is optional at import time so the app still boots
# (and the Supadata path still works) even if it isn't installed.
try:
    from youtube_transcript_api import (
        YouTubeTranscriptApi,
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable,
    )
    _HAS_YTA = True
except Exception:  # pragma: no cover
    _HAS_YTA = False


def _proxy_config():
    """Optional proxy for the free path. YouTube rate-limits datacenter IPs;
    routing through a residential proxy is the production bypass. Driven by
    env, so it costs nothing when unset:
      WEBSHARE_PROXY_USERNAME / WEBSHARE_PROXY_PASSWORD  (Webshare rotating), or
      YT_PROXY_HTTP / YT_PROXY_HTTPS                     (any proxy URL).
    """
    if not _HAS_YTA:
        return None
    ws_user = os.getenv("WEBSHARE_PROXY_USERNAME")
    ws_pass = os.getenv("WEBSHARE_PROXY_PASSWORD")
    http_url = os.getenv("YT_PROXY_HTTP")
    https_url = os.getenv("YT_PROXY_HTTPS")
    try:
        if ws_user and ws_pass:
            from youtube_transcript_api.proxies import WebshareProxyConfig
            return WebshareProxyConfig(proxy_username=ws_user, proxy_password=ws_pass)
        if http_url or https_url:
            from youtube_transcript_api.proxies import GenericProxyConfig
            return GenericProxyConfig(
                http_url=http_url or https_url, https_url=https_url or http_url
            )
    except Exception:  # pragma: no cover - lib/proxy misconfig shouldn't crash boot
        return None
    return None


SUPADATA_BASE = "https://api.supadata.ai/v1"

# A handful of URL shapes people actually paste.
_ID_PATTERNS = [
    r"(?:v=|/shorts/|youtu\.be/|/embed/|/v/)([0-9A-Za-z_-]{11})",
    r"^([0-9A-Za-z_-]{11})$",  # bare id
]


class TranscriptError(Exception):
    """Raised when no transcript could be obtained from any source."""


def extract_video_id(url: str) -> str | None:
    url = (url or "").strip()
    for pattern in _ID_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _from_youtube_library(video_id: str, lang: str = "en") -> tuple[list[dict], str]:
    """Free path. Returns (segments, language_code).

    Prefers the requested language, then English, then ANY available caption
    track — a Hindi-only video must not read as "no captions"; the LLM
    translates downstream.
    """
    if not _HAS_YTA:
        raise TranscriptError("youtube-transcript-api is not installed")

    try:
        # youtube-transcript-api 1.x is instance-based. .fetch() returns a
        # FetchedTranscript; .to_raw_data() gives the classic list of
        # {"text", "start", "duration"} dicts the rest of this code expects.
        proxy = _proxy_config()
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy) if proxy else YouTubeTranscriptApi()
        try:
            fetched = ytt_api.fetch(video_id, languages=[lang, "en", "en-US"])
        except NoTranscriptFound:
            # Nothing in the preferred languages — take whatever exists
            # (TranscriptList iterates manually-created tracks first).
            transcripts = iter(ytt_api.list(video_id))
            first = next(transcripts, None)
            if first is None:
                raise TranscriptError("no_captions")
            fetched = first.fetch()
        raw = fetched.to_raw_data()
        language = getattr(fetched, "language_code", lang) or lang
    except TranscriptError:
        raise
    except (TranscriptsDisabled, NoTranscriptFound):
        raise TranscriptError("no_captions")
    except VideoUnavailable:
        raise TranscriptError("video_unavailable")
    except Exception as exc:  # IP blocks, network, etc.
        raise TranscriptError(f"library_failed: {exc}")

    return [
        {
            "text": seg["text"],
            "start": float(seg["start"]),
            "duration": float(seg.get("duration", 0.0)),
        }
        for seg in raw
        if seg.get("text", "").strip()
    ], language


def _from_supadata(url: str, key: str, lang: str = "en") -> list[dict]:
    """
    Fallback path. Uses Supadata's universal transcript endpoint with
    mode=native (1 credit, captions only). If you want AI transcription of
    uncaptioned videos, drop the mode param — it costs more credits.
    """
    resp = httpx.get(
        f"{SUPADATA_BASE}/transcript",
        params={"url": url, "text": "false", "lang": lang},
        headers={"x-api-key": key},
        timeout=120.0,
    )
    if resp.status_code == 401:
        raise TranscriptError("supadata_bad_key")
    if resp.status_code >= 400:
        raise TranscriptError(f"supadata_error_{resp.status_code}")

    data = resp.json()
    content = data.get("content", [])

    # text=false returns timestamped chunks with offset/duration in ms.
    segments = []
    for seg in content:
        text = seg.get("text", "").strip()
        if not text:
            continue
        segments.append(
            {
                "text": text,
                "start": float(seg.get("offset", 0)) / 1000.0,
                "duration": float(seg.get("duration", 0)) / 1000.0,
            }
        )
    if not segments:
        raise TranscriptError("supadata_empty")
    return segments


# Small in-memory cache so re-summaries, LLM retries, and dev reloads don't
# re-scrape YouTube — every scrape counts toward the IP rate limit.
# ponytail: process-local dict, fine for a single instance; use Redis if you
# run multiple workers and want a shared cache.
_CACHE: dict[str, dict] = {}
_CACHE_MAX = 128


def get_transcript(
    url: str, supadata_key: str | None = None, lang: str = "en"
) -> dict:
    """
    Returns:
        {
          "video_id": str,
          "segments": [...],
          "source": "youtube-transcript-api" | "supadata",
          "language": str,   # BCP-47-ish code of the caption track
        }
    Raises TranscriptError if every available source fails.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise TranscriptError("bad_url")

    cache_key = f"{video_id}:{lang}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    def _cache(result: dict) -> dict:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))  # drop oldest (FIFO)
        _CACHE[cache_key] = result
        return result

    # 1. Free library first.
    try:
        segments, language = _from_youtube_library(video_id, lang=lang)
        return _cache({"video_id": video_id, "segments": segments,
                       "source": "youtube-transcript-api", "language": language})
    except TranscriptError as free_err:
        free_reason = str(free_err)

    # 2. Supadata fallback (only if a key was supplied).
    if supadata_key:
        segments = _from_supadata(url, supadata_key, lang=lang)
        return _cache({"video_id": video_id, "segments": segments,
                       "source": "supadata", "language": lang})

    # Nothing worked and no fallback available.
    if free_reason == "no_captions":
        raise TranscriptError(
            "This video has captions disabled. Add a Supadata key in settings "
            "to transcribe it with AI."
        )
    if "blocking requests from your ip" in free_reason.lower():
        raise TranscriptError(
            "YouTube is temporarily rate-limiting this server's IP (too many "
            "transcript requests). Wait a few minutes and try again, or add a "
            "Supadata key in settings to bypass it."
        )
    raise TranscriptError(
        f"Couldn't fetch a transcript ({free_reason}). "
        "Adding a Supadata key in settings enables an AI fallback."
    )


def fetch_oembed(video_id: str) -> dict:
    """Free, key-less metadata (title, author, thumbnail) via YouTube oEmbed."""
    try:
        resp = httpx.get(
            "https://www.youtube.com/oembed",
            params={
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "format": "json",
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            d = resp.json()
            return {
                "title": d.get("title"),
                "author": d.get("author_name"),
                "thumbnail": d.get("thumbnail_url")
                or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            }
    except Exception:
        pass
    return {
        "title": None,
        "author": None,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
    }
