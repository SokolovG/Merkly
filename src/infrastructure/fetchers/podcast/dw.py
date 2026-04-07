import xml.etree.ElementTree as ET

import httpx

from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode

_DW_RSS_URL = "https://rss.dw.com/xml/podcast-de-langsam"
_ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


class DWPodcastFetcher(IPodcastFetcher):
    async def fetch(self, level: str, language: str) -> PodcastEpisode | None:
        if language != "de":
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(_DW_RSS_URL)
                if response.status_code != 200:
                    return None
            root = ET.fromstring(response.text)
            channel = root.find("channel")
            if channel is None:
                return None
            item = channel.find("item")
            if item is None:
                return None
            title = item.findtext("title", default="")
            enclosure = item.find("enclosure")
            audio_url = enclosure.get("url", "") if enclosure is not None else ""
            duration_str = item.findtext(f"{{{_ITUNES_NS}}}duration", default="0")
            # duration may be "HH:MM:SS", "MM:SS", or plain seconds
            duration_seconds = _parse_duration(duration_str)
            description = item.findtext("description", default="")
            if not audio_url:
                return None
            return PodcastEpisode(
                title=title,
                audio_url=audio_url,
                duration_seconds=duration_seconds,
                description=description,
            )
        except Exception:
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
