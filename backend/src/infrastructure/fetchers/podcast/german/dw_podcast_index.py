import random

import httpx
import structlog

from backend.src.domain.ports.podcast_fetcher import PodcastEpisode
from backend.src.infrastructure.fetchers.podcast.podcast_index import PodcastIndexFetcher

logger = structlog.get_logger(__name__)

_DW_FEED_ID = "1019192"  # DW "Langsam gesprochene Nachrichten" on PodcastIndex


class DWPodcastIndexFetcher(PodcastIndexFetcher):
    """Queries DW historical episode catalog via PodcastIndex feed ID."""

    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        if not self._api_key or not self._api_secret:
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                items = await self._get_feed_episodes(client, _DW_FEED_ID, max_episodes=50)
                random.shuffle(items)
                for item in items:
                    url = item.get("enclosureUrl", "")
                    if url:
                        return PodcastEpisode(
                            title=item.get("title", ""),
                            audio_url=url,
                            duration_seconds=item.get("duration", 0),
                            description=item.get("description", ""),
                        )
        except Exception as e:
            logger.warning("DWPodcastIndexFetcher failed: %s", e)
        return None
