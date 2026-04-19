"""Session controller — reading and listening lesson flows.

State lives in Redis (session:{session_id}, TTL 15 min).
All routes require Authorization: Bearer {BACKEND_API_KEY}.
"""

from litestar import Controller, get, post
from litestar.params import Parameter

from backend.src.presentation.dto.session.requests import (
    StartListeningSessionRequest,
    StartReadingSessionRequest,
    SubmitAnswerRequest,
    SubmitWritingRequest,
)
from backend.src.presentation.responses.base import SuccessResponse


class SessionController(Controller):
    path = "/sessions"

    @post("/reading/start")
    async def start_reading_session(self, data: StartReadingSessionRequest) -> SuccessResponse:
        """Resolve contact → profile → fetch article (pool or live) →
        create Redis session with state=questions → return title+content+questions."""
        raise NotImplementedError

    @post("/listening/start")
    async def start_listening_session(self, data: StartListeningSessionRequest) -> SuccessResponse:
        """Resolve contact → profile → fetch episode (pool or live) →
        create Redis session with state=questions → return title+transcript+questions+audio_url."""
        raise NotImplementedError

    @get("/active")
    async def get_active_session(
        self,
        platform: str = Parameter(query="platform"),
        contact_id: str = Parameter(query="contact_id"),
    ) -> SuccessResponse:
        """Look up Redis for any active session for this contact.
        Returns {session_id, state} or {session_id: None, state: None}."""
        raise NotImplementedError

    @post("/{session_id:str}/answer")
    async def submit_answer(self, session_id: str, data: SubmitAnswerRequest) -> SuccessResponse:
        """Load session from Redis → run LLM review →
        set state=writing (if WRITING in strategy) or state=complete →
        return feedback + writing_available flag."""
        raise NotImplementedError

    @post("/{session_id:str}/writing")
    async def submit_writing(self, session_id: str, data: SubmitWritingRequest) -> SuccessResponse:
        """Load session from Redis (state must be writing) →
        run writing review LLM → create vocab cards →
        set state=complete → return feedback + cards."""
        raise NotImplementedError
