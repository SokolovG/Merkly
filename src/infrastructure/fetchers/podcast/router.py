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
