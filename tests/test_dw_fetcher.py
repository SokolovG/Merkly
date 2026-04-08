"""Tests for DWPodcastFetcher using a fixture RSS feed (no network)."""

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.fetchers.podcast.german.dw import DWPodcastFetcher

# feedparser entries behave like dicts — use plain dicts in fixtures
_ENTRY_WITH_AUDIO = {
    "title": "Langsam gesprochene Nachrichten",
    "enclosures": [{"href": "https://dw.com/ep.mp3", "type": "audio/mpeg"}],
    "itunes_duration": "5:30",
    "summary": "Test episode",
}

_ENTRY_NO_ENCLOSURE = {
    "title": "No audio",
    "enclosures": [],
    "itunes_duration": "0",
    "summary": "",
}

_FEED_WITH_AUDIO = MagicMock(entries=[_ENTRY_WITH_AUDIO])
_FEED_NO_ENTRIES = MagicMock(entries=[])
_FEED_NO_ENCLOSURE = MagicMock(entries=[_ENTRY_NO_ENCLOSURE])


@pytest.mark.asyncio
async def test_happy_path():
    with patch(
        "src.infrastructure.fetchers.podcast.german.dw.feedparser.parse",
        return_value=_FEED_WITH_AUDIO,
    ):
        fetcher = DWPodcastFetcher()
        episode = await fetcher.fetch("B1", "de")
    assert episode is not None
    assert episode.audio_url == "https://dw.com/ep.mp3"
    assert episode.title == "Langsam gesprochene Nachrichten"
    assert episode.duration_seconds == 330  # 5:30


@pytest.mark.asyncio
async def test_empty_feed_returns_none():
    with patch(
        "src.infrastructure.fetchers.podcast.german.dw.feedparser.parse",
        return_value=_FEED_NO_ENTRIES,
    ):
        fetcher = DWPodcastFetcher()
        episode = await fetcher.fetch("B1", "de")
    assert episode is None


@pytest.mark.asyncio
async def test_no_audio_enclosure_returns_none():
    with patch(
        "src.infrastructure.fetchers.podcast.german.dw.feedparser.parse",
        return_value=_FEED_NO_ENCLOSURE,
    ):
        fetcher = DWPodcastFetcher()
        episode = await fetcher.fetch("B1", "de")
    assert episode is None


@pytest.mark.asyncio
async def test_feedparser_exception_returns_none():
    with patch(
        "src.infrastructure.fetchers.podcast.german.dw.feedparser.parse",
        side_effect=Exception("network error"),
    ):
        fetcher = DWPodcastFetcher()
        episode = await fetcher.fetch("B1", "de")
    assert episode is None
