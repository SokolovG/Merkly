import msgspec


class UserProfile(msgspec.Struct):
    telegram_id: int
    username: str | None
    level: str  # "A1" | "A2" | "B1" | "B2" | "C1"
    goal: str  # "travel" | "work" | "conversation" | "general"
    native_lang: str  # "en" | "ru" | "uk" | etc.
    session_minutes: int  # 15 | 30 | 60
    target_lang: str = "de"  # language being learned: "de" | "en" | "es" | "fr" | "it" | "pt"
    reminder_enabled: bool = False
    reminder_time: str = "11:00"  # local time HH:MM
    utc_offset: int = 0  # hours offset from UTC
    created_at: str = ""


class VocabCard(msgspec.Struct):
    word: str
    translation: str
    example_sentence: str
    word_type: str  # "noun" | "verb" | "adjective" | "phrase"
    article: str | None = None  # grammatical article for nouns (language-dependent)
    backend_id: str | None = None  # ID returned by Anki/Mochi after creation


class Session(msgspec.Struct):
    session_id: str
    user_id: int
    date: str  # ISO format
    article_url: str
    article_title: str
    article_text: str
    questions: list[str]
    user_answers: list[str]
    feedback: str
    cards_created: list[VocabCard]
    duration_seconds: int = 0
