"""Presentation-layer converters: domain entities → response DTOs.

All converters are module-level constants — adaptix compiles them once at import time.
`StrEnum` fields need no coercer: StrEnum inherits str, so WordType/Goal/Language/ActivityType
values are already assignment-compatible with `str` fields in msgspec.Struct.
"""

from adaptix.conversion import get_converter

from backend.src.domain.entities import PooledVocabCard, UserProfile, VocabCard
from backend.src.presentation.dto.profile.responses import ProfileResponse
from backend.src.presentation.dto.shared.responses import CardDTO

# VocabCard → CardDTO
# Extra source field `backend_id` is silently ignored by adaptix.
_vocab_card_to_dto = get_converter(VocabCard, CardDTO)


def vocab_card_to_dto(card: VocabCard) -> CardDTO:
    return _vocab_card_to_dto(card)


def pooled_card_to_dto(card: PooledVocabCard) -> CardDTO:
    # Manual conversion: PooledVocabCard has no grammar_note (not in DB schema),
    # so we can't use adaptix here — adaptix 3.0b12 rejects allow_unlinked_optional
    # when the field name matches no source field even with the recipe applied.
    return CardDTO(
        word=card.word,
        translation=card.translation,
        example_sentence=card.example_sentence,
        word_type=str(card.word_type),
        article=card.article,
        grammar_note=None,
    )


def profile_to_response(profile: UserProfile) -> ProfileResponse:
    """Convert UserProfile → ProfileResponse.

    Manual construction because of a deliberate field rename:
    `UserProfile.id: uuid.UUID` → `ProfileResponse.user_id: str`.
    Adaptix field-link API would handle this, but the rename is the only mismatch
    and explicit construction is clearer than a recipe for a single field.
    """
    return ProfileResponse(
        user_id=str(profile.id),
        level=profile.level,
        goal=profile.goal,
        native_lang=profile.native_lang,
        target_lang=profile.target_lang,
        reminder_enabled=profile.reminder_enabled,
        reminder_time=profile.reminder_time,
        utc_offset=profile.utc_offset,
        vocab_card_count=profile.vocab_card_count,
        question_count=profile.question_count,
        episode_duration_min=profile.episode_duration_min,
        learning_strategy=list(profile.learning_strategy),
        vocab_scheduler_enabled=profile.vocab_scheduler_enabled,
        vocab_scheduler_time=profile.vocab_scheduler_time,
        vocab_scheduler_deck_id=profile.vocab_scheduler_deck_id,
    )
