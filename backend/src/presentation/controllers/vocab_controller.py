from dishka.integrations.litestar import FromDishka, inject
from litestar import Controller, get, post
from litestar.exceptions import NotFoundException
from litestar.params import Parameter

from backend.src.application.use_cases.resolve_user import UserResolverUseCase
from backend.src.application.use_cases.vocab_use_case import (
    CaptureWordUseCase,
    GenerateVocabUseCase,
)
from backend.src.domain.enums import Platform
from backend.src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository
from backend.src.presentation.converters import pooled_card_to_dto, vocab_card_to_dto
from backend.src.presentation.dto.shared.responses import CardDTO
from backend.src.presentation.dto.vocab.requests import (
    CaptureWordRequest,
    GenerateVocabRequest,
    RegenerateWordRequest,
)
from backend.src.presentation.dto.vocab.responses import (
    CaptureWordResponse,
    RepeatVocabResponse,
    VocabResponse,
)
from backend.src.presentation.responses.base import SuccessResponse


class VocabController(Controller):
    path = "/vocab"

    @post("/generate")
    @inject
    async def generate_vocab(
        self,
        data: GenerateVocabRequest,
        resolver: FromDishka[UserResolverUseCase],
        generate_uc: FromDishka[GenerateVocabUseCase],
    ) -> SuccessResponse:
        """Serve vocab cards from pool (or live LLM if pool empty)."""
        ctx = await resolver.resolve(data.platform, data.contact_id)
        result = await generate_uc.execute(ctx.profile, data.count, data.force_topic)

        cards = (
            [pooled_card_to_dto(c) for c in result.cards]  # type: ignore[arg-type]
            if result.from_pool
            else [vocab_card_to_dto(c) for c in result.cards]  # type: ignore[arg-type]
        )
        return SuccessResponse(
            data=VocabResponse(topic=result.topic, cards=cards),
            message="Vocab cards served from pool" if result.from_pool else "Vocab cards generated",
        )

    @get("/repeat")
    @inject
    async def repeat_vocab(
        self,
        resolver: FromDishka[UserResolverUseCase],
        vocab_repo: FromDishka[VocabPoolRepository],
        platform: str = Parameter(query="platform"),
        contact_id: str = Parameter(query="contact_id"),
        count: int | None = Parameter(query="count", default=None),
    ) -> SuccessResponse:
        """Return oldest-first cards from vocab_history. No LLM call."""
        try:
            platform_enum = Platform(platform)
        except ValueError:
            raise NotFoundException(detail=f"Unknown platform: {platform!r}") from None

        ctx = await resolver.resolve(platform_enum, contact_id)
        card_count = count or ctx.profile.vocab_card_count

        words = await vocab_repo.get_history_words(
            ctx.profile.id, str(ctx.profile.target_lang), limit=card_count, oldest_first=True
        )
        total_result = await vocab_repo.get_history_words(
            ctx.profile.id, str(ctx.profile.target_lang), limit=10_000, oldest_first=False
        )
        cards = [
            CardDTO(word=w, translation="", example_sentence="", word_type="noun") for w in words
        ]
        return SuccessResponse(
            data=RepeatVocabResponse(cards=cards, total_seen=len(total_result)),
            message="Repeat cards fetched",
        )

    @post("/word")
    @inject
    async def capture_word(
        self,
        data: CaptureWordRequest,
        resolver: FromDishka[UserResolverUseCase],
        capture_uc: FromDishka[CaptureWordUseCase],
    ) -> SuccessResponse:
        """Duplicate check → LLM card generation → return card.

        already_exists=True: word is in vocab history, no LLM call was made.
        Status is always 200; callers discriminate via the already_exists field.
        """
        ctx = await resolver.resolve(data.platform, data.contact_id)
        result = await capture_uc.execute(ctx.profile, data.word, data.context)

        if result.already_exists:
            # No card was generated — return a minimal placeholder.
            # The TG bot shows word_already_exists() message and ignores card data.
            card_dto = CardDTO(
                word=data.word, translation="", example_sentence="", word_type="noun"
            )
        else:
            assert result.card is not None
            card_dto = vocab_card_to_dto(result.card)

        return SuccessResponse(
            data=CaptureWordResponse(
                card=card_dto,
                pool_card_id=result.pool_card_id,
                already_exists=result.already_exists,
            ),
            message="Word already in history" if result.already_exists else "Word captured",
        )

    @post("/word/regenerate")
    @inject
    async def regenerate_word(
        self,
        data: RegenerateWordRequest,
        resolver: FromDishka[UserResolverUseCase],
        capture_uc: FromDishka[CaptureWordUseCase],
    ) -> SuccessResponse:
        """Re-run word capture with explicit context, bypassing duplicate check."""
        ctx = await resolver.resolve(data.platform, data.contact_id)
        result = await capture_uc.execute_regen(ctx.profile, data.word, data.context)
        assert result.card is not None
        return SuccessResponse(
            data=CaptureWordResponse(
                card=vocab_card_to_dto(result.card),
                pool_card_id=result.pool_card_id,
                already_exists=False,
            ),
            message="Word regenerated",
        )
