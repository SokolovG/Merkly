"""Response types mirroring backend DTOs — no import from backend/ package."""

import msgspec


class CardDTO(msgspec.Struct):
    word: str
    translation: str
    example_sentence: str
    word_type: str
    article: str | None = None
    grammar_note: str | None = None


class IdentityLookupResponse(msgspec.Struct):
    user_id: str
    platform: str
    platform_user_id: str


class StartSessionResponse(msgspec.Struct):
    session_id: str
    session_type: str  # "reading" | "listening"
    title: str
    content: str
    questions: list[str]
    audio_url: str | None = None


class ActiveSessionResponse(msgspec.Struct):
    session_id: str | None
    state: str | None  # "questions" | "writing" | None


class AnswerResponse(msgspec.Struct):
    feedback: str
    writing_available: bool
    cards: list[CardDTO]


class WritingResponse(msgspec.Struct):
    feedback: str
    cards: list[CardDTO]


class VocabResponse(msgspec.Struct):
    topic: str
    cards: list[CardDTO]


class RepeatVocabResponse(msgspec.Struct):
    cards: list[CardDTO]
    total_seen: int


class CaptureWordResponse(msgspec.Struct):
    card: CardDTO
    pool_card_id: str
    already_exists: bool = False


class WritingThemeDTO(msgspec.Struct):
    id: str
    theme: str


class WritingThemesResponse(msgspec.Struct):
    themes: list[WritingThemeDTO]


class ProfileResponse(msgspec.Struct):
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


class StartWritingSessionResponse(msgspec.Struct):
    session_id: str
    task: str  # writing task instructions shown to the user
    theme: str
