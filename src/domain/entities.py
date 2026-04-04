import msgspec

from src.domain.enums import Goal, Language, Level, WordType

DEFAULT_VOCAB_CARD_COUNT = 8


class UserDeck(msgspec.Struct):
    name: str
    backend_id: str  # For Anki: deck name (same as name). For Mochi: UUID returned by API.


class UserProfile(msgspec.Struct):
    telegram_id: int
    username: str | None
    level: Level
    goal: Goal
    native_lang: Language
    session_minutes: int
    target_lang: Language = Language.DE
    reminder_enabled: bool = False
    reminder_time: str = "11:00"
    utc_offset: int = 0
    vocab_card_count: int = DEFAULT_VOCAB_CARD_COUNT
    created_at: str = ""
    decks: list[UserDeck] = []
    active_deck_id: str = ""  # backend_id of active deck; empty = use env default


class VocabCard(msgspec.Struct):
    word: str
    translation: str
    example_sentence: str
    word_type: WordType
    article: str | None = None
    backend_id: str | None = None


class Session(msgspec.Struct):
    session_id: str
    user_id: int
    date: str
    article_url: str
    article_title: str
    article_text: str
    questions: list[str]
    user_answers: list[str]
    feedback: str
    cards_created: list[VocabCard]
    duration_seconds: int = 0
