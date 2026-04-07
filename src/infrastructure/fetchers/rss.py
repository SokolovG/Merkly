import logging
import random
import re
import xml.etree.ElementTree as ET

import httpx

from src.domain.ports.article_fetcher import Article, IArticleFetcher
from src.infrastructure.decorators import retry
from src.infrastructure.exceptions import FetcherError

logger = logging.getLogger(__name__)

# Default RSS sources per language — agent can override with source_url
_DEFAULT_SOURCES: dict[str, list[str]] = {
    "de": [
        "https://www.tagesschau.de/xml/rss2/",
        "https://rss.dw.com/rdf/rss-de-news",
    ],
    "en": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.reuters.com/reuters/topNews",
    ],
    "es": [
        "https://www.bbc.com/mundo/index.xml",
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    ],
    "fr": [
        "https://www.france24.com/fr/rss",
        "https://www.lemonde.fr/rss/une.xml",
    ],
    "it": [
        "https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml",
    ],
    "pt": [
        "https://g1.globo.com/rss/g1/",
    ],
}


def _truncate(text: str, max_words: int = 300) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]) + "..."


def _parse_rss_items(xml_text: str) -> list[ET.Element]:
    """Parse RSS items from both RSS 2.0 and RDF/RSS 1.0 formats."""
    root = ET.fromstring(xml_text)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://purl.org/rss/1.0/}item")
    return items


class NewsArticleFetcher(IArticleFetcher):
    """Fetches news articles from RSS feeds. The agent decides which source URL to use."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "LangTutorBot/1.0 (language learning app)"},
        )

    @retry(max_attempts=3, backoff=1.0)
    async def fetch(
        self, level: str, language: str = "de", source_url: str | None = None
    ) -> Article:
        """Fetch from source_url if given, otherwise use a default for the language."""
        url = source_url or _DEFAULT_SOURCES.get(language, _DEFAULT_SOURCES["en"])[0]
        return await self._fetch_from_rss(url, level)

    async def _fetch_from_rss(self, feed_url: str, level: str) -> Article:
        resp = await self._client.get(feed_url)
        resp.raise_for_status()

        items = _parse_rss_items(resp.text)
        if not items:
            raise FetcherError(f"No items found in RSS feed: {feed_url}")

        item = random.choice(items[:10])

        def find_text(el: ET.Element, tag: str) -> str:
            return el.findtext(tag) or el.findtext(f"{{http://purl.org/rss/1.0/}}{tag}") or ""

        title = find_text(item, "title").strip() or "Article"
        link = find_text(item, "link").strip()
        description = find_text(item, "description").strip()

        text = re.sub(r"<[^>]+>", "", description).strip()
        if len(text.split()) < 50 and link:
            text = await self._fetch_page_text(link) or text

        if len(text.split()) < 20:
            raise FetcherError(f"Article text too short from {feed_url}")

        return Article(url=link or feed_url, title=title, text=_truncate(text), level=level)

    async def _fetch_page_text(self, url: str) -> str | None:
        import json

        try:
            resp = await self._client.get(url)
            html = resp.text

            for m in re.finditer(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                html,
                re.DOTALL | re.IGNORECASE,
            ):
                try:
                    data = json.loads(m.group(1))
                    body = data.get("articleBody") or data.get("description", "")
                    if body and len(body.split()) >= 50:
                        return _truncate(body)
                except Exception:
                    continue

            html = re.sub(
                r"<(script|style)[^>]*>.*?</(script|style)>",
                " ",
                html,
                flags=re.DOTALL | re.IGNORECASE,
            )
            text = re.sub(r"<[^>]+>", " ", html)
            return _truncate(re.sub(r"\s+", " ", text).strip())
        except Exception:
            return None
