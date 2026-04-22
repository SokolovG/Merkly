"""Vocab controller — card generation, word capture, repeat."""

import uuid

from dishka.integrations.litestar import FromDishka, inject
from litestar import Controller, get, post
from litestar.exceptions import NotFoundException
from litestar.params import Parameter

from backend.src.application.agent.core import LessonAgent
from backend.src.infrastructure.database.repositories.profile_repo import ProfileRepository
from backend.src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository
from backend.src.presentation.converters import pooled_card_to_dto, vocab_card_to_dto
from backend.src.presentation.dto.shared.responses import CardDTO
from backend.src.presentation.dto.vocab.requests import CaptureWordRequest, RegenerateWordRequest
from backend.src.presentation.dto.vocab.responses import (
    CaptureWordResponse,
    RepeatVocabResponse,
    VocabResponse,
)
from backend.src.presentation.responses.base import SuccessResponse


class VocabController(Controller):
    path = "/vocab"

    @inject
    @get("")
    async def generate_vocab(
        self,
        user_id: str = Parameter(query="user_id"),
        count: int | None = Parameter(query="count", default=None),
        topic: str | None = Parameter(query="topic", default=None),
        *,
        profile_repo: FromDishka[ProfileRepository],
        vocab_repo: FromDishka[VocabPoolRepository],
        agent: FromDishka[LessonAgent],
    ) -> SuccessResponse:
        """Serve vocab cards from pool (or live LLM if pool empty)."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise NotFoundException(detail=f"Invalid user_id: {user_id!r}") from None

        profile = await profile_repo.get_by_id(uid)
        if profile is None:
            raise NotFoundException(detail=f"Profile not found: {user_id}") from None

        card_count = count or profile.vocab_card_count
        pool_cards = await vocab_repo.get_pool_cards(
            profile.id, str(profile.target_lang), card_count
        )

        if pool_cards:
            await vocab_repo.mark_shown(profile.id, [c.id for c in pool_cards])
            return SuccessResponse(
                data=VocabResponse(
                    topic="Vocabulary",
                    cards=[pooled_card_to_dto(c) for c in pool_cards],
                ),
                message="Vocab cards served from pool",
            )

        # Pool empty — generate live
        actual_topic, vocab_cards = await agent.topic_vocab_lesson(
            level=profile.level,
            goal=str(profile.goal),
            native_lang=str(profile.native_lang),
            target_lang=str(profile.target_lang),
            recent_topics=[],
            count=card_count,
            force_topic=topic,
        )
        return SuccessResponse(
            data=VocabResponse(
                topic=actual_topic,
                cards=[vocab_card_to_dto(c) for c in vocab_cards],
            ),
            message="Vocab cards generated",
        )

    @inject
    @get("/repeat")
    async def repeat_vocab(
        self,
        user_id: str = Parameter(query="user_id"),
        count: int | None = Parameter(query="count", default=None),
        *,
        profile_repo: FromDishka[ProfileRepository],
        vocab_repo: FromDishka[VocabPoolRepository],
    ) -> SuccessResponse:
        """Return oldest-first cards from vocab_history. No LLM call."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise NotFoundException(detail=f"Invalid user_id: {user_id!r}") from None

        profile = await profile_repo.get_by_id(uid)
        if profile is None:
            raise NotFoundException(detail=f"Profile not found: {user_id}") from None

        card_count = count or profile.vocab_card_count
        words = await vocab_repo.get_history_words(
            profile.id, str(profile.target_lang), limit=card_count, oldest_first=True
        )
        total_result = await vocab_repo.get_history_words(
            profile.id, str(profile.target_lang), limit=10_000, oldest_first=False
        )
        cards = [
            CardDTO(word=w, translation="", example_sentence="", word_type="noun") for w in words
        ]
        return SuccessResponse(
            data=RepeatVocabResponse(cards=cards, total_seen=len(total_result)),
            message="Repeat cards fetched",
        )

    @inject
    @post("/word")
    async def capture_word(
        self,
        data: CaptureWordRequest,
        profile_repo: FromDishka[ProfileRepository],
        agent: FromDishka[LessonAgent],
    ) -> SuccessResponse:
        """Run +word capture flow: LLM generates card → save to Anki/Mochi → return card."""
        try:
            uid = uuid.UUID(data.user_id)
        except ValueError:
            raise NotFoundException(detail=f"Invalid user_id: {data.user_id!r}") from None

        profile = await profile_repo.get_by_id(uid)
        if profile is None:
            raise NotFoundException(detail=f"Profile not found: {data.user_id}") from None

        card = await agent.capture_word(
            word=data.word,
            target_lang=str(profile.target_lang),
            native_lang=str(profile.native_lang),
            context=data.context,
        )
        return SuccessResponse(
            data=CaptureWordResponse(
                card=vocab_card_to_dto(card),
                pool_card_id=card.backend_id or str(uuid.uuid4()),
            ),
            message="Word captured",
        )

    @inject
    @post("/word/regenerate")
    async def regenerate_word(
        self,
        data: RegenerateWordRequest,
        profile_repo: FromDishka[ProfileRepository],
        agent: FromDishka[LessonAgent],
    ) -> SuccessResponse:
        """Re-run word capture with explicit context → return updated card."""
        try:
            uid = uuid.UUID(data.user_id)
        except ValueError:
            raise NotFoundException(detail=f"Invalid user_id: {data.user_id!r}") from None

        profile = await profile_repo.get_by_id(uid)
        if profile is None:
            raise NotFoundException(detail=f"Profile not found: {data.user_id}") from None

        card = await agent.capture_word(
            word=data.word,
            target_lang=str(profile.target_lang),
            native_lang=str(profile.native_lang),
            context=data.context,
        )
        return SuccessResponse(
            data=CaptureWordResponse(
                card=vocab_card_to_dto(card),
                pool_card_id=card.backend_id or str(uuid.uuid4()),
            ),
            message="Word regenerated",
        )
