"""Transcript layer: URL parsing, language fallback, Supadata conversion."""

import pytest
import respx
from httpx import Response

import transcript
from transcript import extract_video_id, get_transcript, TranscriptError

VID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VID}",
        f"https://youtu.be/{VID}",
        f"https://www.youtube.com/shorts/{VID}",
        f"https://www.youtube.com/embed/{VID}",
        f"https://www.youtube.com/v/{VID}",
        VID,
        f"https://m.youtube.com/watch?foo=1&v={VID}&t=30s",
    ],
)
def test_extract_video_id_shapes(url):
    assert extract_video_id(url) == VID


@pytest.mark.parametrize("url", ["", "not a url", "https://vimeo.com/12345", None])
def test_extract_video_id_garbage(url):
    assert extract_video_id(url) is None


RAW = [{"text": "hello", "start": 0.0, "duration": 2.0}]


class FakeNoTranscriptFound(Exception):
    pass


class FakeFetched:
    def __init__(self, language_code="en"):
        self.language_code = language_code

    def to_raw_data(self):
        return RAW


def _patch_api(monkeypatch, api_cls):
    monkeypatch.setattr(transcript, "_HAS_YTA", True)
    monkeypatch.setattr(transcript, "YouTubeTranscriptApi", api_cls)
    monkeypatch.setattr(transcript, "NoTranscriptFound", FakeNoTranscriptFound)


def test_preferred_language_direct(monkeypatch):
    class API:
        def fetch(self, video_id, languages=None):
            return FakeFetched("en")

    _patch_api(monkeypatch, API)
    tr = get_transcript(f"https://youtu.be/{VID}")
    assert tr["language"] == "en"
    assert tr["source"] == "youtube-transcript-api"
    assert tr["segments"][0]["text"] == "hello"


def test_falls_back_to_any_language(monkeypatch):
    """Hindi-only video: preferred langs missing, first available track wins."""

    class HindiTrack:
        def fetch(self):
            return FakeFetched("hi")

    class API:
        def fetch(self, video_id, languages=None):
            raise FakeNoTranscriptFound()

        def list(self, video_id):
            return iter([HindiTrack()])

    _patch_api(monkeypatch, API)
    tr = get_transcript(f"https://youtu.be/{VID}")
    assert tr["language"] == "hi"
    assert tr["segments"] == RAW


def test_no_tracks_at_all_maps_to_friendly_error(monkeypatch):
    class API:
        def fetch(self, video_id, languages=None):
            raise FakeNoTranscriptFound()

        def list(self, video_id):
            return iter([])

    _patch_api(monkeypatch, API)
    with pytest.raises(TranscriptError, match="Supadata"):
        get_transcript(f"https://youtu.be/{VID}")


@respx.mock
def test_free_fails_then_supadata_with_ms_conversion(monkeypatch):
    class API:
        def fetch(self, video_id, languages=None):
            raise FakeNoTranscriptFound()

        def list(self, video_id):
            return iter([])

    _patch_api(monkeypatch, API)
    respx.get("https://api.supadata.ai/v1/transcript").mock(
        return_value=Response(
            200,
            json={"content": [{"text": "ola", "offset": 1500, "duration": 2500}]},
        )
    )
    tr = get_transcript(f"https://youtu.be/{VID}", supadata_key="sk")
    assert tr["source"] == "supadata"
    assert tr["segments"] == [{"text": "ola", "start": 1.5, "duration": 2.5}]


@respx.mock
def test_supadata_bad_key(monkeypatch):
    class API:
        def fetch(self, video_id, languages=None):
            raise FakeNoTranscriptFound()

        def list(self, video_id):
            return iter([])

    _patch_api(monkeypatch, API)
    respx.get("https://api.supadata.ai/v1/transcript").mock(
        return_value=Response(401, json={})
    )
    with pytest.raises(TranscriptError, match="supadata_bad_key"):
        get_transcript(f"https://youtu.be/{VID}", supadata_key="bad")


def test_bad_url_raises():
    with pytest.raises(TranscriptError, match="bad_url"):
        get_transcript("https://vimeo.com/999")
