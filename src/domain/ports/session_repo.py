from abc import ABC, abstractmethod

from src.domain.entities import Session


class ISessionRepository(ABC):
    @abstractmethod
    async def save(self, session: Session) -> None: ...

    @abstractmethod
    async def get_recent(self, user_id: int, limit: int = 3) -> list[Session]: ...
