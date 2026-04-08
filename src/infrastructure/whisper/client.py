import os
from logging import getLogger

import httpx

from src.infrastructure.exceptions import InfrastructureError

logger = getLogger(__name__)

_MIME_BY_SUFFIX = {
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
}


class WhisperClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._client = httpx.AsyncClient(timeout=1200)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def transcribe(self, audio_path: str) -> str:
        """Send audio file to faster-whisper server, return transcript text."""
        _, suffix = os.path.splitext(audio_path)
        mime_type = _MIME_BY_SUFFIX.get(suffix.lower(), "audio/mpeg")
        filename = os.path.basename(audio_path)
        with open(audio_path, "rb") as f:
            response = await self._client.post(
                f"{self._base_url}/v1/audio/transcriptions",
                files={"file": (filename, f, mime_type)},
                data={"model": "base"},
            )
        if response.status_code != 200:
            raise InfrastructureError(f"Whisper transcription failed: {response.text}")
        return response.json()["text"]
