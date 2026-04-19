import msgspec


class StartReadingSessionRequest(msgspec.Struct):
    """POST /sessions/reading/start"""

    platform: str  # "telegram", "whatsapp", "web"
    contact_id: str  # platform-specific user ID (Telegram int as str)


class StartListeningSessionRequest(msgspec.Struct):
    """POST /sessions/listening/start"""

    platform: str
    contact_id: str


class SubmitAnswerRequest(msgspec.Struct):
    """POST /sessions/{session_id}/answer"""

    answers: list[str]


class SubmitWritingRequest(msgspec.Struct):
    """POST /sessions/{session_id}/writing"""

    text: str
