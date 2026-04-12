import uuid
from abc import ABC, abstractmethod

from src.domain.entities import Session


class ISessionRepository(ABC):
    @abstractmethod
    async def save(self, session: Session, user_id: uuid.UUID) -> None: ...

    @abstractmethod
    async def get_recent(self, user_id: uuid.UUID, limit: int = 3) -> list[Session]: ...
