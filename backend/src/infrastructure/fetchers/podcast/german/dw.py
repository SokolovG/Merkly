import asyncio
import logging
import random

import feedparser

from backend.src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode
from backend.src.infrastructure.fetchers.podcast.utils import parse_duration

logger = logging.getLogger(__name__)

_DW_RSS_URL = "https://rss.dw.com/xml/podcast-de-langsam"


class DWPodcastFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        try:
            loop = asyncio.get_running_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, _DW_RSS_URL)
            if not feed.entries:
                reason = getattr(feed, "bozo_exception", None)
                logger.warning("DWPodcastFetcher: feed has no entries: %s", reason)
                return None
            entries = list(feed.entries)
            random.shuffle(entries)
            for entry in entries:
                audio_url = next(
                    (
                        e["href"]
                        for e in entry.get("enclosures", [])
                        if e.get("type", "").startswith("audio")
                    ),
                    "",
                )
                if audio_url:
                    return PodcastEpisode(
                        title=entry.get("title", ""),
                        audio_url=audio_url,
                        duration_seconds=parse_duration(entry.get("itunes_duration", "0")),
                        description=entry.get("summary", ""),
                    )
            logger.warning("DWPodcastFetcher: no audio enclosures in feed")
            return None
        except Exception as e:
            logger.warning("DWPodcastFetcher failed: %s", e)
            return None
