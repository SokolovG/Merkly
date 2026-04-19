import msgspec


class UpdateProfileRequest(msgspec.Struct, omit_defaults=True):
    """PATCH /profiles/{user_id}"""

    level: str | None = None
    goal: str | None = None
    native_lang: str | None = None
    target_lang: str | None = None
    reminder_enabled: bool | None = None
    reminder_time: str | None = None
    utc_offset: int | None = None
    vocab_card_count: int | None = None
    question_count: int | None = None
    episode_duration_min: int | None = None
    learning_strategy: list[str] | None = None
