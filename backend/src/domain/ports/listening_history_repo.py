import uuid
from abc import ABC, abstractmethod


class IListeningHistoryRepository(ABC):
    @abstractmethod
    async def record(self, user_id: uuid.UUID, episode_url: str, target_lang: str) -> None:
        """Record a served episode in listening_history."""
        ...
