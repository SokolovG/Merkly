import logging
import random

import httpx

from backend.src.domain.constants import LANGUAGE_NAMES
from backend.src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode

logger = logging.getLogger(__name__)


class ItunesPodcastFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        try:
            lang_name = LANGUAGE_NAMES.get(language, language)
            url = (
                f"https://itunes.apple.com/search"
                f"?term={lang_name}+podcast&media=podcast&entity=podcastEpisode&limit=10"
            )
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None
            data = response.json()
            results = data.get("results", [])
            if not results:
                return None
            random.shuffle(results)
            for item in results:
                audio_url = item.get("episodeUrl") or item.get("previewUrl")
                if not audio_url:
                    continue
                return PodcastEpisode(
                    title=item.get("trackName", ""),
                    audio_url=audio_url,
                    duration_seconds=item.get("trackTimeMillis", 0) // 1000,
                    description=item.get("description", ""),
                )
            return None
        except Exception as e:
            logger.warning("ItunesPodcastFetcher failed: %s", e)
            return None
