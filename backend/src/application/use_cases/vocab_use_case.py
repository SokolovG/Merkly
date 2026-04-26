import uuid
from dataclasses import dataclass

import structlog

from backend.src.application.agent.core import LessonAgent
from backend.src.application.background_refiller import BackgroundRefiller
from backend.src.domain.constants import STRIP_ARTICLES
from backend.src.domain.entities import PooledVocabCard, UserProfile, VocabCard
from backend.src.domain.ports.card_gateway import ICardGateway
from backend.src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository
from backend.src.infrastructure.exceptions import InternalServerError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class VocabResult:
    topic: str
    cards: list[VocabCard] | list[PooledVocabCard]
    from_pool: bool


@dataclass(frozen=True)
class WordCaptureResult:
    already_exists: bool
    card: VocabCard | None = None  # None when already_exists=True
    pool_card_id: str = ""


def _normalize_word(word: str) -> str:
    """Strip leading articles for case-insensitive duplicate matching."""
    lower = word.lower().strip()
    for article in STRIP_ARTICLES:
        if lower.startswith(article):
            return lower[len(article) :]
    return lower


class GenerateVocabUseCase:
    def __init__(
        self, agent: LessonAgent, repo: VocabPoolRepository, refiller: BackgroundRefiller
    ) -> None:
        self._agent = agent
        self._repo = repo
        self._refiller = refiller

    async def execute(
        self,
        profile: UserProfile,
        count: int | None = None,
        force_topic: str | None = None,
    ) -> VocabResult:
        try:
            card_count = count or profile.vocab_card_count
            pool_cards = await self._repo.get_pool_cards(
                profile.id, str(profile.target_lang), card_count
            )

            if pool_cards:
                await self._repo.mark_shown(profile.id, [c.id for c in pool_cards])
                self._refiller.schedule_vocab_refill(profile)
                return VocabResult(topic="Vocabulary", cards=pool_cards, from_pool=True)

            actual_topic, vocab_cards = await self._agent.topic_vocab_lesson(
                level=profile.level,
                goal=str(profile.goal),
                native_lang=str(profile.native_lang),
                target_lang=str(profile.target_lang),
                recent_topics=[],
                count=card_count,
                force_topic=force_topic,
            )
            return VocabResult(topic=actual_topic, cards=vocab_cards, from_pool=False)
        except Exception as exc:
            raise InternalServerError(
                message="Failed to generate vocab",
                details={"user_id": str(profile.id), "force_topic": force_topic},
            ) from exc


class CaptureWordUseCase:
    def __init__(
        self, agent: LessonAgent, repo: VocabPoolRepository, card_gateway: ICardGateway
    ) -> None:
        self._agent = agent
        self._repo = repo
        self._card_gateway = card_gateway

    async def execute(
        self,
        profile: UserProfile,
        word: str,
        context: str | None = None,
    ) -> WordCaptureResult:
        """Duplicate check → LLM generation. Returns already_exists=True on duplicate."""
        try:
            history = await self._repo.get_history_words(
                profile.id, str(profile.target_lang), limit=10_000
            )
            normalized_input = _normalize_word(word)
            if any(_normalize_word(w) == normalized_input for w in history):
                return WordCaptureResult(already_exists=True)

            return await self._call_llm(profile, word, context)
        except InternalServerError:
            raise
        except Exception as exc:
            raise InternalServerError(
                message="Failed to capture word",
                details={"user_id": str(profile.id), "word": word},
            ) from exc

    async def execute_regen(
        self,
        profile: UserProfile,
        word: str,
        context: str,
        old_card_id: str | None = None,
    ) -> WordCaptureResult:
        """Bypass duplicate check — user explicitly requested regeneration with new context.

        Deletes old_card_id from the card backend before creating the replacement so the
        user ends up with exactly one card (T36 fix).
        """
        try:
            if old_card_id:
                await self._card_gateway.delete_card(old_card_id)
            return await self._call_llm(profile, word, context)
        except InternalServerError:
            raise
        except Exception as exc:
            raise InternalServerError(
                message="Failed to regenerate word",
                details={"user_id": str(profile.id), "word": word},
            ) from exc

    async def _call_llm(
        self,
        profile: UserProfile,
        word: str,
        context: str | None,
    ) -> WordCaptureResult:
        card = await self._agent.capture_word(
            word=word,
            target_lang=str(profile.target_lang),
            native_lang=str(profile.native_lang),
            context=context,
        )
        return WordCaptureResult(
            already_exists=False,
            card=card,
            pool_card_id=card.backend_id or str(uuid.uuid4()),
        )
