"""BackendClient — typed httpx wrapper for the Merkly backend API.

All requests carry Authorization + X-Trace-ID headers.
Backend wraps responses in {"data": {...}, "message": "..."};
each method unwraps the data field before returning.
"""

import uuid
from typing import Any

import httpx
import msgspec

from src.infrastructure.backend_client.types import (
    ActiveSessionResponse,
    AnswerResponse,
    CaptureWordResponse,
    IdentityLookupResponse,
    ProfileResponse,
    RepeatVocabResponse,
    StartSessionResponse,
    StartWritingSessionResponse,
    VocabResponse,
    WritingResponse,
    WritingThemesResponse,
)


def _unwrap(raw: dict[str, Any]) -> Any:
    return raw.get("data")


class BackendClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "X-Trace-ID": str(uuid.uuid4()),
        }

    async def close(self) -> None:
        await self._client.aclose()

    # --- Identity ---

    async def lookup_identity(
        self, platform: str, contact_id: str
    ) -> IdentityLookupResponse | None:
        response = await self._client.get(
            "/api/identity/lookup",
            params={"platform": platform, "contact_id": contact_id},
            headers=self._headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), IdentityLookupResponse)

    # --- Sessions ---

    async def start_session(self, platform: str, contact_id: str) -> StartSessionResponse:
        """Auto-pick activity from profile strategy."""
        response = await self._client.post(
            "/api/sessions/start",
            json={"platform": platform, "contact_id": contact_id},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), StartSessionResponse)

    async def start_reading_session(self, platform: str, contact_id: str) -> StartSessionResponse:
        response = await self._client.post(
            "/api/sessions/reading/start",
            json={"platform": platform, "contact_id": contact_id},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), StartSessionResponse)

    async def start_listening_session(self, platform: str, contact_id: str) -> StartSessionResponse:
        response = await self._client.post(
            "/api/sessions/listening/start",
            json={"platform": platform, "contact_id": contact_id},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), StartSessionResponse)

    async def get_active_session(self, platform: str, contact_id: str) -> ActiveSessionResponse:
        response = await self._client.get(
            "/api/sessions/active",
            params={"platform": platform, "contact_id": contact_id},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), ActiveSessionResponse)

    async def submit_answer(self, session_id: str, answer: str) -> AnswerResponse:
        response = await self._client.post(
            f"/api/sessions/{session_id}/answer",
            json={"answers": [answer]},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), AnswerResponse)

    async def submit_writing(self, session_id: str, writing: str, mode: str) -> WritingResponse:
        response = await self._client.post(
            f"/api/sessions/{session_id}/writing",
            json={"writing": writing, "mode": mode},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), WritingResponse)

    async def get_writing_themes(
        self, platform: str, contact_id: str, count: int = 1
    ) -> WritingThemesResponse:
        response = await self._client.get(
            "/api/sessions/writing/themes",
            params={"platform": platform, "contact_id": contact_id, "count": count},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), WritingThemesResponse)

    async def start_writing_session(
        self, platform: str, contact_id: str, theme_id: str, mode: str = "article"
    ) -> StartWritingSessionResponse:
        response = await self._client.post(
            "/api/sessions/writing/start",
            json={
                "platform": platform,
                "contact_id": contact_id,
                "theme_id": theme_id,
                "mode": mode,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), StartWritingSessionResponse)

    # --- Vocab ---

    async def generate_vocab(
        self,
        platform: str,
        contact_id: str,
        count: int,
        force_topic: str | None = None,
    ) -> VocabResponse:
        response = await self._client.post(
            "/api/vocab/generate",
            json={
                "platform": platform,
                "contact_id": contact_id,
                "count": count,
                "force_topic": force_topic,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), VocabResponse)

    async def get_repeat(self, platform: str, contact_id: str) -> RepeatVocabResponse:
        response = await self._client.get(
            "/api/vocab/repeat",
            params={"platform": platform, "contact_id": contact_id},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), RepeatVocabResponse)

    async def capture_word(
        self,
        platform: str,
        contact_id: str,
        word: str,
        context: str | None = None,
    ) -> CaptureWordResponse:
        response = await self._client.post(
            "/api/vocab/word",
            json={
                "platform": platform,
                "contact_id": contact_id,
                "word": word,
                "context": context,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), CaptureWordResponse)

    async def regenerate_word(
        self,
        platform: str,
        contact_id: str,
        word: str,
        context: str,
        old_card_id: str | None = None,
    ) -> CaptureWordResponse:
        body: dict[str, Any] = {
            "platform": platform,
            "contact_id": contact_id,
            "word": word,
            "context": context,
        }
        if old_card_id:
            body["old_card_id"] = old_card_id
        response = await self._client.post(
            "/api/vocab/word/regenerate",
            json=body,
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), CaptureWordResponse)

    # --- Profile ---

    async def get_profile(self, user_id: str) -> ProfileResponse:
        response = await self._client.get(
            f"/api/profiles/{user_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), ProfileResponse)

    async def update_profile(self, user_id: str, **fields: Any) -> ProfileResponse:
        response = await self._client.patch(
            f"/api/profiles/{user_id}",
            json={k: v for k, v in fields.items() if v is not None},
            headers=self._headers(),
        )
        response.raise_for_status()
        raw: dict[str, Any] = msgspec.json.decode(response.content)
        return msgspec.convert(_unwrap(raw), ProfileResponse)
