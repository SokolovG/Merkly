import msgspec


class ProfileResponse(msgspec.Struct):
    """Response for GET /profiles/{user_id} and PATCH /profiles/{user_id}."""

    user_id: str
    level: str
    goal: str
    native_lang: str
    target_lang: str
    reminder_enabled: bool
    reminder_time: str
    utc_offset: int
    vocab_card_count: int
    question_count: int
    episode_duration_min: int
    learning_strategy: list[str]
    vocab_scheduler_enabled: bool
    vocab_scheduler_time: str
    vocab_scheduler_deck_id: str = ""
