import xml.etree.ElementTree as ET

import httpx

from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode

_ORF_FEEDS = [
    "https://sound.orf.at/podcast/oe1/oe1-wissen-aktuell/rss",
    "https://sound.orf.at/podcast/oe1/oe1-digitalleben/rss",
]
_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


class ORFPodcastFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        async with httpx.AsyncClient(timeout=15) as client:
            for feed_url in _ORF_FEEDS:
                try:
                    response = await client.get(feed_url)
                    if response.status_code != 200:
                        continue
                    root = ET.fromstring(response.text)
                    channel = root.find("channel")
                    if channel is None:
                        continue
                    item = channel.find("item")
                    if item is None:
                        continue
                    title = item.findtext("title", default="")
                    enclosure = item.find("enclosure")
                    audio_url = enclosure.get("url", "") if enclosure is not None else ""
                    if not audio_url:
                        continue
                    duration_str = item.findtext(f"{{{_ITUNES_NS}}}duration", default="0")
                    duration_seconds = _parse_duration(duration_str)
                    description = item.findtext("description", default="")
                    return PodcastEpisode(
                        title=title,
                        audio_url=audio_url,
                        duration_seconds=duration_seconds,
                        description=description,
                    )
                except Exception:
                    continue
        return None


def _parse_duration(value: str) -> int:
    try:
        parts = value.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(value)
    except (ValueError, AttributeError):
        return 0
