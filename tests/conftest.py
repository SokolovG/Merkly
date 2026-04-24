"""Shared async DB engine + session factory for integration tests."""

import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.src.infrastructure.database.models import (  # noqa: F401 — ensure tables registered
    ArticlePoolModel,
    Base,
    ListeningHistoryModel,
    ListeningPoolModel,
    ProfileModel,
    SessionHistoryModel,
    SessionModel,
    VocabHistoryModel,
    VocabPoolModel,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/merkly_test",
)


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create async engine, build all tables, yield engine, drop tables on teardown."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Yield a fresh AsyncSession per test; rollback on teardown for isolation."""
    async with AsyncSession(bind=db_engine) as session:
        yield session
        await session.rollback()
