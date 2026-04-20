import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.domain.entities import Identity
from backend.src.domain.enums import Platform
from backend.src.domain.ports.identity_repo import IIdentityRepository
from backend.src.infrastructure.database.models.identity_model import IdentityModel

logger = structlog.get_logger(__name__)


class IdentityRepository(IIdentityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: IdentityModel) -> Identity:
        return Identity(
            id=row.id,
            user_id=row.user_id,
            platform=Platform(row.platform),
            platform_user_id=row.platform_user_id,
        )

    async def save(self, identity: Identity) -> None:
        result = await self._session.execute(
            select(IdentityModel).where(
                IdentityModel.platform == str(identity.platform),
                IdentityModel.platform_user_id == identity.platform_user_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            self._session.add(
                IdentityModel(
                    id=identity.id,
                    user_id=identity.user_id,
                    platform=str(identity.platform),
                    platform_user_id=identity.platform_user_id,
                )
            )
        else:
            existing.user_id = identity.user_id
        await self._session.commit()

    async def get_by_platform(self, platform: Platform, platform_user_id: str) -> Identity | None:
        result = await self._session.execute(
            select(IdentityModel).where(
                IdentityModel.platform == str(platform),
                IdentityModel.platform_user_id == platform_user_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_by_user_id(self, user_id: uuid.UUID, platform: Platform) -> Identity | None:
        result = await self._session.execute(
            select(IdentityModel).where(
                IdentityModel.user_id == user_id,
                IdentityModel.platform == str(platform),
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None
