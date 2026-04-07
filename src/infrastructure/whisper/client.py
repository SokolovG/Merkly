import httpx

from src.infrastructure.exceptions import InfrastructureError


class WhisperClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._client = httpx.AsyncClient(timeout=120)

    async def transcribe(self, audio_path: str) -> str:
        """Send audio file to faster-whisper server, return transcript text."""
        with open(audio_path, "rb") as f:
            response = await self._client.post(
                f"{self._base_url}/v1/audio/transcriptions",
                files={"file": ("audio.mp3", f, "audio/mpeg")},
                data={"model": "whisper-1"},
            )
        if response.status_code != 200:
            raise InfrastructureError(f"Whisper transcription failed: {response.text}")
        return response.json()["text"]
