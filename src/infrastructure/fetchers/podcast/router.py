from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.fetchers.podcast.dw import DWPodcastFetcher
from src.infrastructure.fetchers.podcast.itunes import ItunesPodcastFetcher
from src.infrastructure.fetchers.podcast.podcast_index import PodcastIndexFetcher


class PodcastFetcherRouter(IPodcastFetcher):
    def __init__(
        self,
        itunes: ItunesPodcastFetcher,
        podcast_index: PodcastIndexFetcher,
        dw: DWPodcastFetcher,
    ) -> None:
        self._itunes = itunes
        self._podcast_index = podcast_index
        self._dw = dw

    @classmethod
    def build(
        cls, podcast_index_api_key: str, podcast_index_api_secret: str
    ) -> "PodcastFetcherRouter":
        """Build the default router. All source knowledge lives here, not in the DI container."""
        return cls(
            itunes=ItunesPodcastFetcher(),
            podcast_index=PodcastIndexFetcher(
                api_key=podcast_index_api_key,
                api_secret=podcast_index_api_secret,
            ),
            dw=DWPodcastFetcher(),
        )

    async def fetch(self, level: str, language: str) -> PodcastEpisode:
        # 1. Try iTunes (all languages)
        episode = await self._itunes.fetch(level, language)
        if episode:
            return episode
        # 2. Try Podcast Index (all languages, needs API key)
        episode = await self._podcast_index.fetch(level, language)
        if episode:
            return episode
        # 3. DW fallback (German only)
        if language == "de":
            episode = await self._dw.fetch(level, language)
            if episode:
                return episode
        raise InfrastructureError(f"No podcast found for language={language}")
