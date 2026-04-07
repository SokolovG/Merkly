import tempfile

import httpx
from pydub import AudioSegment


class AudioService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60, follow_redirects=True)

    async def download_and_trim(self, audio_url: str, duration_min: int) -> str:
        """Download audio from URL, trim to duration_min minutes, return path to temp file."""
        duration_ms = duration_min * 60 * 1000
        suffix = ".m4a" if ".m4a" in audio_url else ".mp3"
        response = await self._client.get(audio_url)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        audio = AudioSegment.from_file(tmp_path)
        if len(audio) > duration_ms:
            audio = audio[:duration_ms]
        out_path = tmp_path.replace(suffix, "_trimmed.mp3")
        audio.export(out_path, format="mp3")
        return out_path
