import ipaddress
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
        """Download first duration_min minutes of audio via Range header."""
        _validate_audio_url(audio_url)
        max_bytes = duration_min * 1_000_000  # ~128kbps, rough upper bound
        suffix = ".m4a" if ".m4a" in audio_url else ".mp3"
        response = await self._client.get(audio_url, headers={"Range": f"bytes=0-{max_bytes}"})
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            return tmp.name
