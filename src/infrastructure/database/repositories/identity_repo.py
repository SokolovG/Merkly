import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Identity
from src.domain.enums import Platform
from src.domain.ports.identity_repo import IIdentityRepository
from src.infrastructure.database.models.identity_model import IdentityModel

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
        stmt = pg_insert(IdentityModel).values(
            id=identity.id,
            user_id=identity.user_id,
            platform=str(identity.platform),
            platform_user_id=identity.platform_user_id,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="identities_platform_platform_user_id_key",
            set_={"user_id": stmt.excluded.user_id},
        )
        await self._session.execute(stmt)
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
