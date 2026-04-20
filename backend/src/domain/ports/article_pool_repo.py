from abc import ABC, abstractmethod
from uuid import UUID

from backend.src.domain.entities import PooledArticle


class IArticlePoolRepository(ABC):
    @abstractmethod
    async def pool_count(self, user_id: UUID, target_lang: str) -> int: ...

    @abstractmethod
    async def get_oldest(self, user_id: UUID, target_lang: str) -> PooledArticle | None: ...

    @abstractmethod
    async def mark_served(self, article_id: UUID) -> None: ...

    @abstractmethod
    async def add_to_pool(self, user_id: UUID, articles: list[PooledArticle]) -> None: ...
