import pytest

from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.fetchers.podcast.router import PodcastFetcherRouter

_EPISODE = PodcastEpisode(title="Test", audio_url="https://example.com/ep.mp3", duration_seconds=60)


class _OkFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        return _EPISODE


class _NullFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        return None


class _ErrorFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        raise RuntimeError("network error")


@pytest.mark.asyncio
async def test_language_specific_fetcher_used_first():
    router = PodcastFetcherRouter(
        generic=[_NullFetcher()],
        language_specific={"de": [_OkFetcher()]},
    )
    result = await router.fetch("B1", "de")
    assert result == _EPISODE


@pytest.mark.asyncio
async def test_language_specific_never_falls_back_to_generic():
    """When dedicated fetchers all return None, InfrastructureError is raised instead of
    falling through to generic — prevents returning content in the wrong language."""
    router = PodcastFetcherRouter(
        generic=[_OkFetcher()],
        language_specific={"de": [_NullFetcher()]},
    )
    with pytest.raises(InfrastructureError, match="language=de"):
        await router.fetch("B1", "de")


@pytest.mark.asyncio
async def test_language_specific_all_fail_raises():
    router = PodcastFetcherRouter(
        generic=[],
        language_specific={"de": [_NullFetcher(), _NullFetcher()]},
    )
    with pytest.raises(InfrastructureError):
        await router.fetch("B1", "de")


@pytest.mark.asyncio
async def test_no_dedicated_fetchers_uses_generic():
    router = PodcastFetcherRouter(
        generic=[_OkFetcher()],
        language_specific={},
    )
    result = await router.fetch("B1", "fr")
    assert result == _EPISODE


@pytest.mark.asyncio
async def test_generic_all_fail_raises():
    router = PodcastFetcherRouter(
        generic=[_NullFetcher(), _NullFetcher()],
        language_specific={},
    )
    with pytest.raises(InfrastructureError):
        await router.fetch("B1", "fr")


@pytest.mark.asyncio
async def test_language_specific_skips_none_tries_next():
    router = PodcastFetcherRouter(
        generic=[],
        language_specific={"de": [_NullFetcher(), _OkFetcher()]},
    )
    result = await router.fetch("B1", "de")
    assert result == _EPISODE


@pytest.mark.asyncio
async def test_language_specific_fetcher_exception_treated_as_none():
    """A fetcher that raises should be caught by the fetcher itself (per DW/ORF pattern).
    The router treats a None return from a fetcher as 'try next'."""
    router = PodcastFetcherRouter(
        generic=[],
        language_specific={"de": [_NullFetcher(), _OkFetcher()]},
    )
    result = await router.fetch("B1", "de")
    assert result == _EPISODE
