import ipaddress
import os
import subprocess
import tempfile
from urllib.parse import urlparse

import httpx

from src.infrastructure.exceptions import InfrastructureError

_ALLOWED_SCHEMES = {"http", "https"}


def _validate_audio_url(url: str) -> None:
    """Reject non-HTTP schemes and private/loopback IP addresses (SSRF prevention)."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise InfrastructureError(f"Disallowed URL scheme '{parsed.scheme}' in audio URL")
    hostname = parsed.hostname or ""
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise InfrastructureError(f"Private/reserved IP address in audio URL: {hostname}")
    except ValueError:
        pass  # hostname is a domain name, not an IP — fine


class AudioService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60, follow_redirects=True)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def download(self, audio_url: str, duration_min: int = 5) -> str:
        """Download and trim audio to duration_min minutes using pydub."""
        _validate_audio_url(audio_url)
        # Generous byte cap: covers ~320kbps to bound download size, pydub trims precisely after
        max_bytes = duration_min * 3_000_000
        suffix = ".m4a" if ".m4a" in audio_url else ".mp3"
        response = await self._client.get(audio_url, headers={"Range": f"bytes=0-{max_bytes}"})
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as raw:
            raw.write(response.content)
            raw_path = raw.name
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as out:
                out_path = out.name
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-t",
                    str(duration_min * 60),
                    "-i",
                    raw_path,
                    "-c:a",
                    "libmp3lame",
                    out_path,
                ],
                check=True,
                capture_output=True,
            )
        finally:
            os.unlink(raw_path)
        return out_path
