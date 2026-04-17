"""Integration tests for SessionRepository — requires real Postgres."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Session, UserProfile, VocabCard
from src.domain.enums import Goal, Language, WordType
from src.infrastructure.database.repositories.profile_repo import ProfileRepository
from src.infrastructure.database.repositories.session_repo import SessionRepository

pytestmark = pytest.mark.integration


def _make_profile() -> UserProfile:
    return UserProfile(
        username="sessionuser",
        level="B1",
        goal=Goal.TRAVEL,
        native_lang=Language.EN,
        target_lang=Language.DE,
    )


def _make_session(session_id: str) -> Session:
    return Session(
        session_id=session_id,
        user_id=uuid.uuid4(),  # overridden by repo.save user_id param
        date="2025-01-01",
        article_url=f"https://example.com/article-{session_id}",
        article_title="Test Article",
        article_text="Some test article text.",
        questions=["Q1?", "Q2?"],
        user_answers=["A1", "A2"],
        feedback="Good job!",
        cards_created=[
            VocabCard(
                word="laufen",
                translation="to run",
                example_sentence="Ich laufe schnell.",
                word_type=WordType.VERB,
            )
        ],
    )


async def test_save_and_get_recent(db_session: AsyncSession) -> None:
    repo = SessionRepository(db_session)
    profile = _make_profile()
    await ProfileRepository(db_session).save(profile)

    session = _make_session(session_id=str(uuid.uuid4()))
    await repo.save(session, profile.id)

    recent = await repo.get_recent(profile.id, limit=3)
    assert len(recent) == 1
    assert recent[0].article_url == session.article_url
    assert recent[0].questions == session.questions
    assert recent[0].feedback == session.feedback


async def test_get_recent_limit(db_session: AsyncSession) -> None:
    session_repo = SessionRepository(db_session)
    profile_repo = ProfileRepository(db_session)
    profile = _make_profile()
    await profile_repo.save(profile)

    saved_ids: list[str] = []
    for _ in range(5):
        sid = str(uuid.uuid4())
        saved_ids.append(sid)
        session = _make_session(session_id=sid)
        await session_repo.save(session, profile.id)

    recent = await session_repo.get_recent(profile.id, limit=2)
    assert len(recent) == 2
    # Most recent first — the last saved session should be first
    assert recent[0].session_id == saved_ids[-1]


async def test_get_recent_empty(db_session: AsyncSession) -> None:
    profile_repo = ProfileRepository(db_session)
    profile = _make_profile()
    await profile_repo.save(profile)

    session_repo = SessionRepository(db_session)
    recent = await session_repo.get_recent(profile.id, limit=3)
    assert recent == []
