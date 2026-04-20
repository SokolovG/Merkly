import logging

from backend.src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode
from backend.src.infrastructure.exceptions import InfrastructureError
from backend.src.infrastructure.fetchers.podcast.constants import LANGUAGE_PODCAST_FETCHERS
from backend.src.infrastructure.fetchers.podcast.german.dw_podcast_index import (
    DWPodcastIndexFetcher,
)
from backend.src.infrastructure.fetchers.podcast.itunes import ItunesPodcastFetcher
from backend.src.infrastructure.fetchers.podcast.podcast_index import PodcastIndexFetcher

logger = logging.getLogger(__name__)


class PodcastFetcherRouter(IPodcastFetcher):
    def __init__(
        self,
        generic: list[IPodcastFetcher],
        language_specific: dict[str, list[IPodcastFetcher]],
    ) -> None:
        self._generic = generic
        self._language_specific = language_specific

    @classmethod
    def build(
        cls,
        podcast_index_api_key: str,
        podcast_index_api_secret: str,
    ) -> "PodcastFetcherRouter":
        """Build the default router. Language sources come from LANGUAGE_PODCAST_FETCHERS."""
        lang_specific: dict[str, list[IPodcastFetcher]] = {
            lang: [fetcher_cls() for fetcher_cls in fetcher_classes]
            for lang, fetcher_classes in LANGUAGE_PODCAST_FETCHERS.items()
        }
        lang_specific.setdefault("de", []).append(
            DWPodcastIndexFetcher(
                api_key=podcast_index_api_key,
                api_secret=podcast_index_api_secret,
            )
        )
        return cls(
            generic=[
                ItunesPodcastFetcher(),
                PodcastIndexFetcher(
                    api_key=podcast_index_api_key,
                    api_secret=podcast_index_api_secret,
                ),
            ],
            language_specific=lang_specific,
        )

    async def fetch(self, level: str, language: str) -> PodcastEpisode:
        lang_fetchers = self._language_specific.get(language, [])
        if lang_fetchers:
            # Language has dedicated fetchers — never fall back to generic (avoids wrong language)
            for fetcher in lang_fetchers:
                episode = await fetcher.fetch(level, language)
                if episode:
                    return episode
                logger.warning("%s returned None for language=%s", type(fetcher).__name__, language)
            raise InfrastructureError(f"All dedicated fetchers failed for language={language}")
        # No dedicated fetchers — use generic sources
        for fetcher in self._generic:
            episode = await fetcher.fetch(level, language)
            if episode:
                return episode
        raise InfrastructureError(f"No podcast found for language={language}")
