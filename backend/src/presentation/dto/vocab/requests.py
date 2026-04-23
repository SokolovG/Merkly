import msgspec

from backend.src.domain.enums import Platform


class GenerateVocabRequest(msgspec.Struct):
    """POST /vocab/generate"""

    platform: Platform
    contact_id: str
    count: int | None = None
    force_topic: str | None = None


class CaptureWordRequest(msgspec.Struct):
    """POST /vocab/word"""

    platform: Platform
    contact_id: str
    word: str
    context: str | None = None


class RegenerateWordRequest(msgspec.Struct):
    """POST /vocab/word/regenerate"""

    platform: Platform
    contact_id: str
    word: str
    context: str  # Required for regeneration
