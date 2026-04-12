import os
import time

import httpx
import structlog

from src.infrastructure.exceptions import InfrastructureError

logger = structlog.get_logger(__name__)

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
        logger.info("transcribe_start", integration="whisper", file=filename)
        t0 = time.monotonic()
        with open(audio_path, "rb") as f:
            response = await self._client.post(
                f"{self._base_url}/v1/audio/transcriptions",
                files={"file": (filename, f, mime_type)},
                data={"model": "base"},
            )
        if response.status_code != 200:
            logger.warning("transcribe_failed", integration="whisper", status=response.status_code)
            raise InfrastructureError(f"Whisper transcription failed: {response.text}")
        latency_ms = round((time.monotonic() - t0) * 1000)
        logger.info("transcribe_complete", integration="whisper", latency_ms=latency_ms)
        return response.json()["text"]
