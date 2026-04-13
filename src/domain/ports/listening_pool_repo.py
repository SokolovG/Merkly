import uuid
from abc import ABC, abstractmethod

from src.domain.entities import PooledListeningLesson


class IListeningPoolRepository(ABC):
    @abstractmethod
    async def pool_count(self, user_id: uuid.UUID, target_lang: str) -> int: ...

    @abstractmethod
    async def get_oldest(
        self, user_id: uuid.UUID, target_lang: str
    ) -> PooledListeningLesson | None: ...

    @abstractmethod
    async def mark_served(self, lesson_id: uuid.UUID) -> None: ...

    @abstractmethod
    async def add_to_pool(
        self, user_id: uuid.UUID, lessons: list[PooledListeningLesson]
    ) -> None: ...
