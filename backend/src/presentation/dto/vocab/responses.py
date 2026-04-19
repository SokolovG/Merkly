import msgspec

from backend.src.presentation.dto.shared.responses import CardDTO


class VocabResponse(msgspec.Struct):
    """Response for GET /vocab."""

    topic: str
    cards: list[CardDTO]


class RepeatVocabResponse(msgspec.Struct):
    """Response for GET /vocab/repeat."""

    cards: list[CardDTO]
    total_seen: int


class CaptureWordResponse(msgspec.Struct):
    """Response for POST /vocab/word."""

    card: CardDTO
    pool_card_id: str
