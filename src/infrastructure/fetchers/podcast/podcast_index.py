import hashlib
import time

import httpx

from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode


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

    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        if not self._api_key or not self._api_secret:
            return None
        try:
            headers = self._auth_headers()
            async with httpx.AsyncClient(timeout=15) as client:
                search_resp = await client.get(
                    f"https://api.podcastindex.org/api/1.0/search/byterm"
                    f"?q={language}+podcast&pretty",
                    headers=headers,
                )
                if search_resp.status_code != 200:
                    return None
                feeds = search_resp.json().get("feeds", [])
                if not feeds:
                    return None
                feed_id = feeds[0].get("id")
                if not feed_id:
                    return None
                # Fetch recent episodes for this feed
                episodes_resp = await client.get(
                    f"https://api.podcastindex.org/api/1.0/episodes/byfeedid"
                    f"?id={feed_id}&max=5",
                    headers=self._auth_headers(),
                )
                if episodes_resp.status_code != 200:
                    return None
                items = episodes_resp.json().get("items", [])
                if not items:
                    return None
                item = items[0]
                return PodcastEpisode(
                    title=item.get("title", ""),
                    audio_url=item.get("enclosureUrl", ""),
                    duration_seconds=item.get("duration", 0),
                    description=item.get("description", ""),
                )
        except Exception:
            return None
