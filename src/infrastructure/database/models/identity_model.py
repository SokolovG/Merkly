import uuid

from sqlalchemy import UUID, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class IdentityModel(Base):
    __tablename__ = "identities"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    platform_user_id: Mapped[str] = mapped_column(Text, nullable=False)
