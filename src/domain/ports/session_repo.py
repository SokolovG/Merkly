from typing import Protocol

from src.domain.entities import Session


class ISessionRepository(Protocol):
    async def save(self, session: Session) -> None: ...
    async def get_recent(self, user_id: int, limit: int = 3) -> list[Session]: ...
