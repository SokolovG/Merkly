from abc import ABC, abstractmethod

from src.domain.entities import UserProfile


class IProfileRepository(ABC):
    @abstractmethod
    async def get(self, messenger_id: int) -> UserProfile | None: ...

    @abstractmethod
    async def save(self, profile: UserProfile) -> None: ...

    @abstractmethod
    async def all(self) -> list[UserProfile]: ...

    @abstractmethod
    async def all_with_reminders(self) -> list[UserProfile]: ...

    @abstractmethod
    async def get_due_for_reminder(self) -> list[UserProfile]: ...
