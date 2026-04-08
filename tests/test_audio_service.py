"""Tests for AudioService — uses respx to mock httpx without network."""

import os

import httpx
import pytest
import respx

from src.infrastructure.audio import AudioService, _validate_audio_url
from src.infrastructure.exceptions import InfrastructureError

# ── URL validation ────────────────────────────────────────────────────────────


def test_validate_accepts_https():
    _validate_audio_url("https://cdn.example.com/episode.mp3")  # no exception


def test_validate_accepts_http():
    _validate_audio_url("http://cdn.example.com/episode.mp3")  # no exception


def test_validate_rejects_private_ip():
    with pytest.raises(InfrastructureError, match="Private"):
        _validate_audio_url("http://192.168.1.1/audio.mp3")


def test_validate_rejects_loopback():
    with pytest.raises(InfrastructureError, match="Private"):
        _validate_audio_url("http://127.0.0.1/audio.mp3")


def test_validate_rejects_link_local():
    with pytest.raises(InfrastructureError, match="Private"):
        _validate_audio_url("http://169.254.169.254/latest/meta-data/")


def test_validate_rejects_non_http_scheme():
    with pytest.raises(InfrastructureError, match="scheme"):
        _validate_audio_url("ftp://example.com/audio.mp3")


def test_validate_rejects_file_scheme():
    with pytest.raises(InfrastructureError, match="scheme"):
        _validate_audio_url("file:///etc/passwd")


# ── Download ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_download_writes_temp_file_and_returns_path():
    audio_bytes = b"fake-mp3-data"
    respx.get("https://cdn.example.com/episode.mp3").mock(
        return_value=httpx.Response(206, content=audio_bytes)
    )
    service = AudioService()
    try:
        path = await service.download("https://cdn.example.com/episode.mp3", duration_min=3)
        assert path.endswith(".mp3")
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read() == audio_bytes
    finally:
        if os.path.exists(path):
            os.unlink(path)
        await service.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_download_uses_m4a_suffix_for_m4a_url():
    respx.get("https://cdn.example.com/episode.m4a").mock(
        return_value=httpx.Response(206, content=b"fake-m4a")
    )
    service = AudioService()
    try:
        path = await service.download("https://cdn.example.com/episode.m4a", duration_min=3)
        assert path.endswith(".m4a")
    finally:
        if os.path.exists(path):
            os.unlink(path)
        await service.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_download_raises_on_http_error():
    respx.get("https://cdn.example.com/episode.mp3").mock(return_value=httpx.Response(403))
    service = AudioService()
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await service.download("https://cdn.example.com/episode.mp3")
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_download_raises_on_invalid_url():
    service = AudioService()
    try:
        with pytest.raises(InfrastructureError):
            await service.download("http://10.0.0.1/internal.mp3")
    finally:
        await service.aclose()
