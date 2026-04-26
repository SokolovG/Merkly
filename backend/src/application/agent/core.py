from dataclasses import dataclass

from backend.src.application.agent.reading_agent import ReadingAgent
from backend.src.application.agent.vocab_agent import VocabAgent
from backend.src.application.agent.writing_agent import WritingAgent
from backend.src.domain.constants import DEFAULT_QUESTION_COUNT
from backend.src.domain.entities import DEFAULT_VOCAB_CARD_COUNT, VocabCard
from backend.src.domain.exceptions import WordCaptureError  # noqa: F401 — re-export for compat
from backend.src.domain.ports.article_fetcher import IArticleFetcher
from backend.src.domain.ports.card_gateway import ICardGateway
from backend.src.domain.ports.llm_gateway import ILLMGateway


@dataclass
class LessonResult:
    article_title: str
    article_url: str
    article_text: str
    questions: list[str]
    feedback: str
    cards_created: list[VocabCard]


class LessonAgent:
    """Facade that composes ReadingAgent, VocabAgent, and WritingAgent.

    Deprecated: Inject specific agents directly. This class exists only to
    avoid breaking pool_jobs.py and BackgroundRefiller during the transition.
    """

    def __init__(
        self,
        llm: ILLMGateway,
        fetcher: IArticleFetcher,
        card_gateway: ICardGateway,
    ) -> None:
        self._reading = ReadingAgent(llm=llm, fetcher=fetcher, card_gateway=card_gateway)
        self._vocab = VocabAgent(llm=llm, fetcher=fetcher, card_gateway=card_gateway)
        self._writing = WritingAgent(llm=llm, fetcher=fetcher, card_gateway=card_gateway)

    # ── Reading ───────────────────────────────────────────────────────────────

    async def prepare_reading_lesson(
        self,
        level: str,
        goal: str,
        native_lang: str,
        target_lang: str,
        recent_topics: list[str],
        question_count: int = DEFAULT_QUESTION_COUNT,
    ) -> tuple[str, str, str, list[str]]:
        return await self._reading.prepare_reading_lesson(
            level=level,
            goal=goal,
            native_lang=native_lang,
            target_lang=target_lang,
            recent_topics=recent_topics,
            question_count=question_count,
        )

    async def review_answers(
        self,
        article_text: str,
        questions: list[str],
        answers: list[str],
        level: str,
        native_lang: str,
        target_lang: str,
    ) -> tuple[str, list[VocabCard]]:
        return await self._reading.review_answers(
            article_text=article_text,
            questions=questions,
            answers=answers,
            level=level,
            native_lang=native_lang,
            target_lang=target_lang,
        )

    # ── Writing ───────────────────────────────────────────────────────────────

    async def generate_writing_task(
        self,
        article_text: str,
        target_lang: str,
        level: str,
        mode: str = "sentences",
    ) -> str:
        return await self._writing.generate_writing_task(
            article_text=article_text,
            target_lang=target_lang,
            level=level,
            mode=mode,
        )

    async def generate_writing_themes(
        self,
        target_lang: str,
        native_lang: str,
        level: str,
        count: int = 5,
    ) -> list[str]:
        return await self._writing.generate_writing_themes(
            target_lang=target_lang,
            native_lang=native_lang,
            level=level,
            count=count,
        )

    async def generate_standalone_writing_task(
        self,
        theme: str,
        target_lang: str,
        level: str,
        mode: str = "article",
    ) -> str:
        return await self._writing.generate_standalone_writing_task(
            theme=theme,
            target_lang=target_lang,
            level=level,
            mode=mode,
        )

    async def review_writing(
        self,
        writing_task: str,
        user_writing: str,
        level: str,
        native_lang: str,
        target_lang: str,
        mode: str = "sentences",
    ) -> tuple[str, list[VocabCard]]:
        return await self._writing.review_writing(
            writing_task=writing_task,
            user_writing=user_writing,
            level=level,
            native_lang=native_lang,
            target_lang=target_lang,
            mode=mode,
        )

    # ── Vocab ─────────────────────────────────────────────────────────────────

    async def topic_vocab_lesson(
        self,
        level: str,
        goal: str,
        native_lang: str,
        target_lang: str,
        recent_topics: list[str],
        count: int = DEFAULT_VOCAB_CARD_COUNT,
        force_topic: str | None = None,
        pool_mode: bool = False,
    ) -> tuple[str, list[VocabCard]]:
        return await self._vocab.topic_vocab_lesson(
            level=level,
            goal=goal,
            native_lang=native_lang,
            target_lang=target_lang,
            recent_topics=recent_topics,
            count=count,
            force_topic=force_topic,
            pool_mode=pool_mode,
        )

    async def vocab_only_lesson(
        self,
        level: str,
        native_lang: str,
        target_lang: str,
    ) -> list[VocabCard]:
        return await self._vocab.vocab_only_lesson(
            level=level,
            native_lang=native_lang,
            target_lang=target_lang,
        )

    async def capture_word(
        self,
        word: str,
        target_lang: str,
        native_lang: str,
        context: str | None = None,
        deck_id: str | None = None,
    ) -> VocabCard:
        return await self._vocab.capture_word(
            word=word,
            target_lang=target_lang,
            native_lang=native_lang,
            context=context,
            deck_id=deck_id,
        )
