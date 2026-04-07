import tempfile

import httpx


class AudioService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60, follow_redirects=True)

    async def download(self, audio_url: str) -> str:
        """Download audio from URL, return path to temp file."""
        suffix = ".m4a" if ".m4a" in audio_url else ".mp3"
        response = await self._client.get(audio_url)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            return tmp.name
