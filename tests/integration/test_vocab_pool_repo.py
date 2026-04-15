"""Integration tests for VocabPoolRepository — requires real Postgres."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import UserProfile, VocabCard
from src.domain.enums import Goal, Language, WordType
from src.infrastructure.database.repositories.profile_repo import ProfileRepository
from src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository

pytestmark = pytest.mark.integration


def _make_profile(messenger_id: int) -> UserProfile:
    return UserProfile(
        messenger_id=messenger_id,
        username="vocabuser",
        level="B1",
        goal=Goal.TRAVEL,
        native_lang=Language.EN,
        target_lang=Language.DE,
    )


def _make_card(word: str) -> VocabCard:
    return VocabCard(
        word=word,
        translation="to run",
        example_sentence="Ich laufe.",
        word_type=WordType.VERB,
    )


async def test_pool_count_empty(db_session: AsyncSession) -> None:
    profile_repo = ProfileRepository(db_session)
    profile = _make_profile(messenger_id=62345)
    await profile_repo.save(profile)

    repo = VocabPoolRepository(db_session)
    count = await repo.pool_count(profile.id, str(profile.target_lang))
    assert count == 0


async def test_add_to_pool_and_count(db_session: AsyncSession) -> None:
    profile_repo = ProfileRepository(db_session)
    profile = _make_profile(messenger_id=62346)
    await profile_repo.save(profile)

    repo = VocabPoolRepository(db_session)
    cards = [_make_card("laufen"), _make_card("spielen"), _make_card("lesen")]
    await repo.add_to_pool(profile.id, cards, str(profile.target_lang))

    count = await repo.pool_count(profile.id, str(profile.target_lang))
    assert count == 3


async def test_get_pool_cards_order(db_session: AsyncSession) -> None:
    profile_repo = ProfileRepository(db_session)
    profile = _make_profile(messenger_id=62347)
    await profile_repo.save(profile)

    repo = VocabPoolRepository(db_session)
    cards = [_make_card("aaa"), _make_card("bbb"), _make_card("ccc")]
    await repo.add_to_pool(profile.id, cards, str(profile.target_lang))

    result = await repo.get_pool_cards(profile.id, str(profile.target_lang), count=2)
    assert len(result) == 2
    # Oldest first (insertion order)
    assert result[0].word == "aaa"
    assert result[1].word == "bbb"


async def test_mark_shown_moves_to_history(db_session: AsyncSession) -> None:
    profile_repo = ProfileRepository(db_session)
    profile = _make_profile(messenger_id=62348)
    await profile_repo.save(profile)

    repo = VocabPoolRepository(db_session)
    cards = [_make_card("gehen"), _make_card("kommen")]
    await repo.add_to_pool(profile.id, cards, str(profile.target_lang))

    pool_cards = await repo.get_pool_cards(profile.id, str(profile.target_lang), count=10)
    assert len(pool_cards) == 2

    # Mark the first card as shown
    await repo.mark_shown(profile.id, [pool_cards[0].id])

    count = await repo.pool_count(profile.id, str(profile.target_lang))
    assert count == 1

    history = await repo.get_history_words(
        profile.id, str(profile.target_lang), limit=10, oldest_first=True
    )
    assert "gehen" in history


async def test_clear_pool(db_session: AsyncSession) -> None:
    profile_repo = ProfileRepository(db_session)
    profile = _make_profile(messenger_id=62349)
    await profile_repo.save(profile)

    repo = VocabPoolRepository(db_session)
    cards = [_make_card("eins"), _make_card("zwei"), _make_card("drei")]
    await repo.add_to_pool(profile.id, cards, str(profile.target_lang))

    deleted = await repo.clear_pool(profile.id, str(profile.target_lang))
    assert deleted == 3

    count = await repo.pool_count(profile.id, str(profile.target_lang))
    assert count == 0


async def test_add_to_pool_dedup(db_session: AsyncSession) -> None:
    profile_repo = ProfileRepository(db_session)
    profile = _make_profile(messenger_id=62350)
    await profile_repo.save(profile)

    repo = VocabPoolRepository(db_session)
    # Add and mark a word as shown
    cards = [_make_card("laufen")]
    await repo.add_to_pool(profile.id, cards, str(profile.target_lang))
    pool_cards = await repo.get_pool_cards(profile.id, str(profile.target_lang), count=10)
    await repo.mark_shown(profile.id, [pool_cards[0].id])

    # Now try adding the same word again — should be deduped against history
    await repo.add_to_pool(profile.id, [_make_card("laufen")], str(profile.target_lang))

    count = await repo.pool_count(profile.id, str(profile.target_lang))
    assert count == 0
