import re
from dataclasses import dataclass
from logging import getLogger

from src.application.agent.prompts import build_system_prompt, lang_name
from src.domain.entities import UserProfile
from src.domain.ports.llm_gateway import Message
from src.domain.ports.podcast_fetcher import IPodcastFetcher
from src.infrastructure.audio import AudioService
from src.infrastructure.exceptions import InfrastructureError
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.whisper.client import WhisperClient

logger = getLogger(__name__)


@dataclass
class AudioLesson:
    audio_path: str
    title: str
    questions: list[str]
    transcript: str
    episode_url: str


class ListeningAgent:
    def __init__(
        self,
        podcast_fetcher: IPodcastFetcher,
        audio: AudioService,
        whisper: WhisperClient,
        llm: LLMClient,
    ) -> None:
        self._fetcher = podcast_fetcher
        self._audio = audio
        self._whisper = whisper
        self._llm = llm

    async def prepare_lesson(self, profile: UserProfile) -> AudioLesson:
        """Fetch podcast, download+trim, transcribe, generate questions."""
        episode = await self._fetcher.fetch(profile.level, profile.target_lang.value)
        if episode is None:
            raise InfrastructureError(f"No podcast found for language={profile.target_lang.value}")
        audio_path = await self._audio.download(episode.audio_url, profile.episode_duration_min)
        transcript = await self._whisper.transcribe(audio_path)
        questions = await self._generate_questions(
            transcript, profile.level, profile.target_lang.value, profile.question_count
        )
        return AudioLesson(audio_path, episode.title, questions, transcript, episode.audio_url)

    async def _generate_questions(
        self,
        transcript: str,
        level: str,
        target_lang: str,
        question_count: int,
    ) -> list[str]:
        name = lang_name(target_lang)
        prompt = (
            f"Based on the following podcast transcript in {name},"
            f" generate exactly {question_count} comprehension questions for a {level} student. "
            f"Write the questions in {name.upper()}, numbered 1. 2. 3. etc. "
            f"Only output the numbered questions, no other text.\n\n"
            f"Transcript:\n{transcript[:3000]}"
        )
        response = await self._llm.complete(
            [
                Message(role="system", content=build_system_prompt(target_lang)),
                Message(role="user", content=prompt),
            ]
        )
        return self._parse_questions(response.content or "", question_count)

    @staticmethod
    def _parse_questions(text: str, count: int) -> list[str]:
        questions = []
        for line in text.strip().split("\n"):
            match = re.match(r"^\d+[.)]\s+(.+)", line.strip())
            if match:
                questions.append(match.group(1).strip())
        return questions[:count] or ["What did you understand from the podcast?"]
