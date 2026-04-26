import msgspec

from backend.src.presentation.dto.shared.responses import CardDTO


class StartSessionResponse(msgspec.Struct):
    """Response for POST /sessions/reading/start and POST /sessions/listening/start."""

    session_id: str
    session_type: str  # "reading" | "listening"
    title: str
    content: str
    questions: list[str]
    audio_url: str | None = None  # Only for listening sessions


class ActiveSessionResponse(msgspec.Struct):
    """Response for GET /sessions/active."""

    session_id: str | None
    state: str | None  # "questions" | "writing" | None


class AnswerResponse(msgspec.Struct):
    """Response for POST /sessions/{session_id}/answer."""

    feedback: str
    writing_available: bool
    cards: list[CardDTO]
    session_type: str


class WritingResponse(msgspec.Struct):
    """Response for POST /sessions/{session_id}/writing."""

    feedback: str
    cards: list[CardDTO]


class WritingThemeDTO(msgspec.Struct):
    """A single writing theme from the pool, with its DB id."""

    id: str
    theme: str


class WritingThemesResponse(msgspec.Struct):
    """Response for GET /sessions/writing/themes."""

    themes: list[WritingThemeDTO]


class StartWritingSessionResponse(msgspec.Struct):
    """Response for POST /sessions/writing/start."""

    session_id: str
    task: str  # writing task instructions to show the user
    theme: str
