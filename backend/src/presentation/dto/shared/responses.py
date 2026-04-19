import msgspec


class CardDTO(msgspec.Struct):
    """Flashcard representation used in vocab and session responses."""

    word: str
    translation: str
    example_sentence: str
    word_type: str  # "noun" | "verb" | "adjective" | "phrase"
    article: str | None = None
    grammar_note: str | None = None
