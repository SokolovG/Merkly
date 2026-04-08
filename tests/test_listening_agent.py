"""Tests for ListeningAgent — all I/O mocked, no network or disk."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.listening_service import AudioLesson, ListeningAgent
from src.domain.entities import UserProfile
from src.domain.enums import Goal, Language
from src.domain.ports.podcast_fetcher import IPodcastFetcher, PodcastEpisode
from src.infrastructure.exceptions import InfrastructureError

_PROFILE = UserProfile(
    telegram_id=1,
    username="test",
    level="B1",
    goal=Goal.GENERAL,
    native_lang=Language.EN,
    target_lang=Language.DE,
    session_minutes=10,
    episode_duration_min=3,
    question_count=3,
)

_EPISODE = PodcastEpisode(
    title="Test Episode",
    audio_url="https://cdn.example.com/ep.mp3",
    duration_seconds=180,
)

_TRANSCRIPT = "Das ist ein Test. Wir lernen Deutsch."


def _make_agent(
    fetcher: IPodcastFetcher | None = None,
    audio_path: str = "/tmp/test.mp3",
    transcript: str = _TRANSCRIPT,
    llm_response: str = "1. Was ist das Thema?\n2. Wer spricht?\n3. Was lernst du?",
) -> ListeningAgent:
    mock_fetcher = fetcher or AsyncMock(
        spec=IPodcastFetcher, fetch=AsyncMock(return_value=_EPISODE)
    )
    mock_audio = MagicMock()
    mock_audio.download = AsyncMock(return_value=audio_path)
    mock_whisper = MagicMock()
    mock_whisper.transcribe = AsyncMock(return_value=transcript)
    mock_llm = MagicMock()
    mock_response = MagicMock(content=llm_response)
    mock_llm.complete = AsyncMock(return_value=mock_response)
    return ListeningAgent(
        podcast_fetcher=mock_fetcher,
        audio=mock_audio,
        whisper=mock_whisper,
        llm=mock_llm,
    )


@pytest.mark.asyncio
async def test_prepare_lesson_happy_path():
    agent = _make_agent()
    lesson = await agent.prepare_lesson(_PROFILE)
    assert isinstance(lesson, AudioLesson)
    assert lesson.audio_path == "/tmp/test.mp3"
    assert lesson.title == "Test Episode"
    assert lesson.transcript == _TRANSCRIPT
    assert len(lesson.questions) == 3


@pytest.mark.asyncio
async def test_prepare_lesson_propagates_fetcher_error():
    failing_fetcher = AsyncMock(spec=IPodcastFetcher)
    failing_fetcher.fetch = AsyncMock(side_effect=InfrastructureError("all fetchers failed"))
    agent = _make_agent(fetcher=failing_fetcher)
    with pytest.raises(InfrastructureError, match="all fetchers failed"):
        await agent.prepare_lesson(_PROFILE)


@pytest.mark.asyncio
async def test_prepare_lesson_llm_empty_response_gives_fallback():
    agent = _make_agent(llm_response="")
    lesson = await agent.prepare_lesson(_PROFILE)
    assert lesson.questions == ["What did you understand from the podcast?"]


@pytest.mark.asyncio
async def test_prepare_lesson_llm_partial_questions():
    agent = _make_agent(llm_response="1. Only one question here")
    lesson = await agent.prepare_lesson(_PROFILE)
    assert lesson.questions == ["Only one question here"]


@pytest.mark.asyncio
async def test_prepare_lesson_truncates_to_question_count():
    agent = _make_agent(llm_response="1. Q1\n2. Q2\n3. Q3\n4. Q4\n5. Q5")
    lesson = await agent.prepare_lesson(_PROFILE)
    assert len(lesson.questions) == _PROFILE.question_count


@pytest.mark.asyncio
async def test_prepare_lesson_uses_profile_language():
    mock_fetcher = AsyncMock(spec=IPodcastFetcher)
    mock_fetcher.fetch = AsyncMock(return_value=_EPISODE)
    agent = _make_agent(fetcher=mock_fetcher)
    await agent.prepare_lesson(_PROFILE)
    mock_fetcher.fetch.assert_called_once_with(_PROFILE.level, _PROFILE.target_lang.value)


@pytest.mark.asyncio
async def test_prepare_lesson_uses_episode_duration_from_profile():
    mock_audio = MagicMock()
    mock_audio.download = AsyncMock(return_value="/tmp/ep.mp3")
    mock_fetcher = AsyncMock(spec=IPodcastFetcher, fetch=AsyncMock(return_value=_EPISODE))
    mock_whisper = MagicMock(transcribe=AsyncMock(return_value=_TRANSCRIPT))
    mock_llm = MagicMock(complete=AsyncMock(return_value=MagicMock(content="1. Q1\n2. Q2\n3. Q3")))
    agent = ListeningAgent(
        podcast_fetcher=mock_fetcher,
        audio=mock_audio,
        whisper=mock_whisper,
        llm=mock_llm,
    )
    await agent.prepare_lesson(_PROFILE)
    mock_audio.download.assert_called_once_with(_EPISODE.audio_url, _PROFILE.episode_duration_min)
