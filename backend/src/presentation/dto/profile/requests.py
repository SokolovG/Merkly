import msgspec

from backend.src.domain.enums import ActivityType, Goal, Language


class UpdateProfileRequest(msgspec.Struct, omit_defaults=True):
    """PATCH /profiles/{user_id}"""

    level: str | None = None
    goal: Goal | None = None
    native_lang: Language | None = None
    target_lang: Language | None = None
    reminder_enabled: bool | None = None
    reminder_time: str | None = None
    utc_offset: int | None = None
    vocab_card_count: int | None = None
    question_count: int | None = None
    episode_duration_min: int | None = None
    learning_strategy: list[ActivityType] | None = None
