import logging

import httpx

from src.domain.constants import LANGUAGE_NAMES
from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode

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
            # Pick first result that has an episodeUrl
            for item in results:
                audio_url = item.get("episodeUrl") or item.get("previewUrl")
                if not audio_url:
                    continue
                title = item.get("trackName", "")
                duration_ms = item.get("trackTimeMillis", 0)
                duration_seconds = duration_ms // 1000 if duration_ms else 0
                description = item.get("description", "")
                return PodcastEpisode(
                    title=title,
                    audio_url=audio_url,
                    duration_seconds=duration_seconds,
                    description=description,
                )
            return None
        except Exception as e:
            logger.warning("ItunesPodcastFetcher failed: %s", e)
            return None
