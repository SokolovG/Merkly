import msgspec

from backend.src.domain.enums import Platform


class StartSessionRequest(msgspec.Struct):
    """POST /sessions/start — auto-picks activity from profile strategy."""

    platform: Platform
    contact_id: str


class StartReadingSessionRequest(msgspec.Struct):
    """POST /sessions/reading/start"""

    platform: Platform
    contact_id: str


class StartListeningSessionRequest(msgspec.Struct):
    """POST /sessions/listening/start"""

    platform: Platform
    contact_id: str


class SubmitAnswerRequest(msgspec.Struct):
    """POST /sessions/{session_id}/answer"""

    answers: list[str]


class SubmitWritingRequest(msgspec.Struct):
    """POST /sessions/{session_id}/writing"""

    text: str
