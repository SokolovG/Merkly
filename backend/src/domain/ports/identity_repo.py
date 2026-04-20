import uuid
from abc import ABC, abstractmethod

from backend.src.domain.entities import Identity
from backend.src.domain.enums import Platform


class IIdentityRepository(ABC):
    @abstractmethod
    async def save(self, identity: Identity) -> None: ...

    @abstractmethod
    async def get_by_platform(
        self, platform: Platform, platform_user_id: str
    ) -> Identity | None: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: uuid.UUID, platform: Platform) -> Identity | None: ...
