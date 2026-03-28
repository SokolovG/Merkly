from typing import Protocol

import msgspec


class Article(msgspec.Struct):
    url: str
    title: str
    text: str  # truncated to ~400 words
    level: str  # "A2" | "B1" | "B2"


class IArticleFetcher(Protocol):
    async def fetch(self, level: str, language: str, source_url: str | None = None) -> Article: ...
