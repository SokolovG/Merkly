import asyncio
import logging

import feedparser

from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode
from src.infrastructure.fetchers.podcast.utils import parse_duration

logger = logging.getLogger(__name__)

_DW_RSS_URL = "https://rss.dw.com/xml/podcast-de-langsam"


class DWPodcastFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        try:
            loop = asyncio.get_running_loop()
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
                duration_seconds=parse_duration(entry.get("itunes_duration", "0")),
                description=entry.get("summary", ""),
            )
        except Exception as e:
            logger.warning("DWPodcastFetcher failed: %s", e)
            return None
