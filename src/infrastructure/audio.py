import tempfile

import httpx


class AudioService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60, follow_redirects=True)

    async def download(self, audio_url: str, duration_min: int = 5) -> str:
        """Download first duration_min minutes of audio via Range header."""
        max_bytes = duration_min * 1_000_000  # ~128kbps, rough upper bound
        suffix = ".m4a" if ".m4a" in audio_url else ".mp3"
        response = await self._client.get(audio_url, headers={"Range": f"bytes=0-{max_bytes}"})
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            return tmp.name
