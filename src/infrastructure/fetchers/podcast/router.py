from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.fetchers.podcast.constants import LANGUAGE_PODCAST_FETCHERS
from src.infrastructure.fetchers.podcast.itunes import ItunesPodcastFetcher
from src.infrastructure.fetchers.podcast.podcast_index import PodcastIndexFetcher


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
        cls, podcast_index_api_key: str, podcast_index_api_secret: str
    ) -> "PodcastFetcherRouter":
        """Build the default router. Language sources come from LANGUAGE_PODCAST_FETCHERS."""
        return cls(
            generic=[
                ItunesPodcastFetcher(),
                PodcastIndexFetcher(
                    api_key=podcast_index_api_key,
                    api_secret=podcast_index_api_secret,
                ),
            ],
            language_specific={
                lang: [cls() for cls in fetcher_classes]
                for lang, fetcher_classes in LANGUAGE_PODCAST_FETCHERS.items()
            },
        )

    async def fetch(self, level: str, language: str) -> PodcastEpisode:
        for fetcher in self._language_specific.get(language, []):
            episode = await fetcher.fetch(level, language)
            if episode:
                return episode
        for fetcher in self._generic:
            episode = await fetcher.fetch(level, language)
            if episode:
                return episode
        raise InfrastructureError(f"No podcast found for language={language}")
