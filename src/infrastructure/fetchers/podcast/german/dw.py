import asyncio
import logging

import feedparser

from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode

logger = logging.getLogger(__name__)

_DW_RSS_URL = "https://rss.dw.com/xml/podcast-de-langsam"


class DWPodcastFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        try:
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, _DW_RSS_URL)
            if not feed.entries:
                logger.warning("DWPodcastFetcher: feed has no entries")
                return None
            entry = feed.entries[0]
            audio_url = next(
                (
                    e["href"]
                    for e in entry.get("enclosures", [])
                    if e.get("type", "").startswith("audio")
                ),
                "",
            )
            if not audio_url:
                logger.warning("DWPodcastFetcher: no audio enclosure in first entry")
                return None
            return PodcastEpisode(
                title=entry.get("title", ""),
                audio_url=audio_url,
                duration_seconds=_parse_duration(entry.get("itunes_duration", "0")),
                description=entry.get("summary", ""),
            )
        except Exception as e:
            logger.warning("DWPodcastFetcher failed: %s", e)
            return None


def _parse_duration(value: str) -> int:
    try:
        parts = value.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(value)
    except (ValueError, AttributeError):
        return 0
