from abc import ABC, abstractmethod

import msgspec


class PodcastEpisode(msgspec.Struct):
    title: str
    audio_url: str
    duration_seconds: int
    description: str = ""
    transcript: str | None = None


class IPodcastFetcher(ABC):
    @abstractmethod
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        """Return an episode, or None if exhausted."""
