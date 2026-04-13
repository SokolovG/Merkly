import asyncio
import logging
import random

import feedparser

from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode
from src.infrastructure.fetchers.podcast.utils import parse_duration

logger = logging.getLogger(__name__)

_ORF_FEEDS = [
    "https://podcast.orf.at/podcast/oe1/oe1_wissen_aktuell/oe1_wissen_aktuell.xml",
    "https://podcast.orf.at/podcast/oe1/oe1_digitalleben/oe1_digitalleben.xml",
    "https://podcast.orf.at/podcast/oe1/oe1_journale/oe1_journale.xml",
]


class ORFPodcastFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        loop = asyncio.get_running_loop()
        for feed_url in _ORF_FEEDS:
            try:
                feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
                if not feed.entries:
                    reason = getattr(feed, "bozo_exception", None)
                    logger.warning("ORF feed %s: no entries: %s", feed_url, reason)
                    continue
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
            except Exception as e:
                logger.warning("ORF feed %s failed: %s", feed_url, e)
                continue
        logger.warning("ORFPodcastFetcher: no audio enclosures across all feeds")
        return None
