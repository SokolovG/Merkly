import uuid

import msgspec

from src.domain.constants import DEFAULT_EPISODE_DURATION_MIN, DEFAULT_QUESTION_COUNT
from src.domain.enums import ActivityType, Goal, Language, MessengerType, WordType

DEFAULT_VOCAB_CARD_COUNT = 8
DEFAULT_REMINDER_TIME = "11:00"
DEFAULT_VOCAB_SCHEDULER_TIME = "09:00"


class UserDeck(msgspec.Struct):
    name: str
    backend_id: str  # For Anki: deck name (same as name). For Mochi: UUID returned by API.


class UserProfile(msgspec.Struct):
    messenger_id: int
    username: str | None
    level: str
    goal: Goal
    native_lang: Language
    target_lang: Language = Language.DE
    messenger_type: MessengerType = MessengerType.TELEGRAM
    reminder_enabled: bool = False
    reminder_time: str = DEFAULT_REMINDER_TIME
    utc_offset: int = 0
    vocab_card_count: int = DEFAULT_VOCAB_CARD_COUNT
    created_at: str = ""
    decks: list[UserDeck] = []
    active_deck_id: str = ""  # backend_id of active deck; empty = use env default
    vocab_scheduler_enabled: bool = False
    vocab_scheduler_time: str = DEFAULT_VOCAB_SCHEDULER_TIME  # HH:MM in user's local time
    vocab_scheduler_deck_id: str = ""  # backend_id of target deck; empty = use active_deck_id
    question_count: int = DEFAULT_QUESTION_COUNT  # Questions per session/listening/writing
    episode_duration_min: int = DEFAULT_EPISODE_DURATION_MIN  # Preferred podcast clip length
    learning_strategy: list[ActivityType] = msgspec.field(
        default_factory=lambda: [
            ActivityType.READING,
            ActivityType.WRITING,
            ActivityType.LISTENING,
            ActivityType.VOCAB,
        ]
    )
    id: uuid.UUID = msgspec.field(
        default_factory=uuid.uuid4
    )  # Internal UUID — generated on construction, persisted on first save


class VocabCard(msgspec.Struct):
    word: str
    translation: str
    example_sentence: str
    word_type: WordType
    article: str | None = None
    grammar_note: str | None = None
    backend_id: str | None = None


class PooledVocabCard(msgspec.Struct):
    id: uuid.UUID  # DB primary key — required for mark_shown
    word: str
    translation: str
    example_sentence: str
    word_type: WordType
    article: str | None = None
    target_lang: str = "de"


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
