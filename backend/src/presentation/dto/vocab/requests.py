import msgspec


class CaptureWordRequest(msgspec.Struct):
    """POST /vocab/word"""

    user_id: str  # UUID as str
    word: str
    context: str | None = None


class RegenerateWordRequest(msgspec.Struct):
    """POST /vocab/word/regenerate"""

    user_id: str
    word: str
    context: str  # Required for regeneration
