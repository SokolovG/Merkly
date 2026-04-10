from abc import ABC, abstractmethod

from src.domain.enums import ActivityType


class ISessionHistoryRepository(ABC):
    @abstractmethod
    async def has_seen(self, user_id: int, url: str) -> bool:
        """True if this user has been served this URL for any activity type."""
        ...

    @abstractmethod
    async def record(self, user_id: int, url: str, activity_type: ActivityType) -> None:
        """Record that user was served this URL."""
        ...
