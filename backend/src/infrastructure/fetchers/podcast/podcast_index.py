import hashlib
import logging
import random
import time

import httpx

from backend.src.domain.constants import LANGUAGE_NAMES
from backend.src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode

logger = logging.getLogger(__name__)


class PodcastIndexFetcher(IPodcastFetcher):
    def __init__(self, api_key: str, api_secret: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret

    def _auth_headers(self) -> dict:
        auth_date = str(int(time.time()))
        auth_hash = hashlib.sha1(
            f"{self._api_key}{self._api_secret}{auth_date}".encode()
        ).hexdigest()
        return {
            "X-Auth-Key": self._api_key,
            "X-Auth-Date": auth_date,
            "Authorization": auth_hash,
            "User-Agent": "LangTutorBot/1.0",
        }

    async def _get_feed_episodes(
        self,
        client: httpx.AsyncClient,
        feed_id: str,
        max_episodes: int,
    ) -> list[dict]:
        """Return episode dicts from PodcastIndex. Returns [] on any failure."""
        resp = await client.get(
            f"https://api.podcastindex.org/api/1.0/episodes/byfeedid"
            f"?id={feed_id}&max={max_episodes}",
            headers=self._auth_headers(),
        )
        if resp.status_code != 200:
            logger.warning("PodcastIndexFetcher episodes fetch failed: %s", resp.status_code)
            return []
        return resp.json().get("items", [])

    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        if not self._api_key or not self._api_secret:
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                lang_name = LANGUAGE_NAMES.get(language, language)
                search_resp = await client.get(
                    f"https://api.podcastindex.org/api/1.0/search/byterm"
                    f"?q={lang_name}+podcast&language={language}&pretty",
                    headers=self._auth_headers(),
                )
                if search_resp.status_code != 200:
                    return None
                feeds = search_resp.json().get("feeds", [])
                for feed in feeds[:3]:
                    feed_id = feed.get("id")
                    if not feed_id:
                        continue
                    items = await self._get_feed_episodes(client, str(feed_id), max_episodes=10)
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
            logger.warning("PodcastIndexFetcher failed: %s", e)
        return None
