"""Unit tests for VocabRefillService — no DB needed, fully mocked."""

from unittest.mock import AsyncMock, MagicMock

from src.application.vocab_refill_service import VocabRefillService
from src.domain.constants import POOL_THRESHOLD
from src.domain.entities import UserProfile, VocabCard
from src.domain.enums import Goal, Language, WordType


def _make_profile() -> UserProfile:
    return UserProfile(
        messenger_id=1,
        username="test",
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


async def test_no_refill_when_pool_full() -> None:
    profile = _make_profile()
    agent = MagicMock()
    repo = MagicMock()
    repo.pool_count = AsyncMock(return_value=POOL_THRESHOLD)

    service = VocabRefillService(agent=agent, repo=repo)
    result = await service.refill_if_needed(profile)

    assert result is False
    agent.topic_vocab_lesson.assert_not_called()


async def test_refill_when_pool_below_threshold() -> None:
    profile = _make_profile()
    agent = MagicMock()
    repo = MagicMock()
    repo.pool_count = AsyncMock(return_value=POOL_THRESHOLD - 1)
    repo.get_history_words = AsyncMock(return_value=[])
    cards = [_make_card("laufen")]
    agent.topic_vocab_lesson = AsyncMock(return_value=("travel", cards))
    repo.add_to_pool = AsyncMock()

    service = VocabRefillService(agent=agent, repo=repo)
    result = await service.refill_if_needed(profile)

    assert result is True
    agent.topic_vocab_lesson.assert_called_once()
    call_kwargs = agent.topic_vocab_lesson.call_args.kwargs
    assert call_kwargs["level"] == "B1"
    assert call_kwargs["target_lang"] == "de"
    repo.add_to_pool.assert_called_once_with(profile.id, cards, "de")


async def test_refill_passes_history_words_as_hint() -> None:
    profile = _make_profile()
    agent = MagicMock()
    repo = MagicMock()
    repo.pool_count = AsyncMock(return_value=POOL_THRESHOLD - 1)
    repo.get_history_words = AsyncMock(return_value=["laufen", "spielen"])
    agent.topic_vocab_lesson = AsyncMock(return_value=("topic", []))
    repo.add_to_pool = AsyncMock()

    service = VocabRefillService(agent=agent, repo=repo)
    await service.refill_if_needed(profile)

    agent.topic_vocab_lesson.assert_called_once()
    call_kwargs = agent.topic_vocab_lesson.call_args.kwargs
    assert call_kwargs["recent_topics"] == ["laufen", "spielen"]


async def test_add_to_pool_called_with_cards() -> None:
    profile = _make_profile()
    agent = MagicMock()
    repo = MagicMock()
    repo.pool_count = AsyncMock(return_value=POOL_THRESHOLD - 1)
    repo.get_history_words = AsyncMock(return_value=[])
    returned_cards = [_make_card(f"word{i}") for i in range(5)]
    agent.topic_vocab_lesson = AsyncMock(return_value=("topic", returned_cards))
    repo.add_to_pool = AsyncMock()

    service = VocabRefillService(agent=agent, repo=repo)
    await service.refill_if_needed(profile)

    repo.add_to_pool.assert_called_once_with(profile.id, returned_cards, str(profile.target_lang))
