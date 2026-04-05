import logging
from dataclasses import dataclass
from enum import Enum

from src.application.agent.prompts import (
    build_review_prompt,
    build_system_prompt,
    build_topic_vocab_prompt,
    build_vocab_prompt,
    build_word_capture_prompt,
    build_writing_review_prompt,
    build_writing_task_prompt,
    lang_name,
)
from src.application.agent.tools import READING_TOOL_SCHEMAS, TOOL_SCHEMAS, AgentTools
from src.domain.entities import DEFAULT_VOCAB_CARD_COUNT, VocabCard
from src.domain.exceptions import WordCaptureError
from src.domain.ports.article_fetcher import IArticleFetcher
from src.domain.ports.card_gateway import ICardGateway
from src.domain.ports.llm_gateway import ILLMGateway, Message
from src.infrastructure.exceptions import CardBackendError, LLMError


@dataclass
class LessonResult:
    article_title: str
    article_url: str
    article_text: str
    questions: list[str]
    feedback: str
    cards_created: list[VocabCard]


class CardBackend(Enum):
    MOCHI = "mochi"
    ANKI = "anki"


logger = logging.getLogger(__name__)

_MAX_AGENT_ITERATIONS = 10


class LessonAgent:
    def __init__(
        self,
        llm: ILLMGateway,
        fetcher: IArticleFetcher,
        anki: ICardGateway,
    ) -> None:
        self._llm = llm
        self._fetcher = fetcher
        self._anki = anki

    async def prepare_lesson(
        self,
        level: str,
        goal: str,
        native_lang: str,
        target_lang: str,
        session_minutes: int,
        recent_topics: list[str],
    ) -> tuple[str, str, str, list[str]]:
        """Fetch article and generate questions. Returns (title, url, text, questions)."""
        tools = AgentTools(self._fetcher, self._anki, target_lang)

        history_note = ""
        if recent_topics:
            history_note = (
                f"Recent topics covered: {', '.join(recent_topics[-3:])}. Pick something different."
            )

        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=(
                    f"Prepare a {lang_name(target_lang)} lesson for a {level} student. "
                    f"Goal: {goal}. Native language: {lang_name(native_lang)}. "
                    f"{history_note}\n\n"
                    f"1. Fetch a {lang_name(target_lang)} article\n"
                    f"2. Return EXACTLY 3 comprehension questions IN "
                    f"{lang_name(target_lang).upper()} (numbered 1. 2. 3.)\n"
                    "Do not do anything else yet."
                ),
            ),
        ]

        for _ in range(_MAX_AGENT_ITERATIONS):
            response = await self._llm.complete(messages, tools=TOOL_SCHEMAS)

            if response.tool_calls:
                tool_results = []
                for tc in response.tool_calls:
                    result = await tools.execute(tc.name, tc.arguments)
                    tool_results.append(f"[{tc.name}]: {result}")

                messages.append(Message(role="assistant", content=response.content or ""))
                messages.append(Message(role="user", content="\n".join(tool_results)))
                continue

            if response.content:
                questions = self._parse_questions(response.content)
                article = tools.fetched_article
                if article and questions:
                    return article.title, article.url, article.text, questions

            break

        # Fallback if agent loop didn't produce clean output
        article = tools.fetched_article
        if article:
            return (
                article.title,
                article.url,
                article.text,
                [
                    "What is the main topic of this article?",
                    "What are the key points mentioned in the article?",
                    "What did you learn from this article?",
                ],
            )
        raise RuntimeError("Agent failed to fetch article")

    async def review_answers(
        self,
        article_text: str,
        questions: list[str],
        answers: list[str],
        level: str,
        native_lang: str,
        target_lang: str,
    ) -> tuple[str, list[VocabCard]]:
        """Review student answers and give feedback. No flashcards — comprehension only."""
        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=build_review_prompt(
                    article_text, questions, answers, level, native_lang, target_lang
                ),
            ),
        ]

        feedback_text = ""

        for _ in range(_MAX_AGENT_ITERATIONS):
            response = await self._llm.complete(messages, tools=READING_TOOL_SCHEMAS)

            if response.content:
                feedback_text = response.content
            break

        return feedback_text, []

    async def generate_writing_task(
        self,
        article_text: str,
        target_lang: str,
        level: str,
        mode: str = "sentences",
    ) -> str:
        """Return a writing task prompt string based on the article (no tools needed)."""
        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=build_writing_task_prompt(article_text, target_lang, level, mode),
            ),
        ]
        response = await self._llm.complete(messages, tools=[])
        return (
            response.content
            or "Write 2–3 sentences about something you found interesting in the article."
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
        """Review student writing, give feedback, create cards for mistakes."""
        tools = AgentTools(self._fetcher, self._anki, target_lang)
        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=build_writing_review_prompt(
                    writing_task, user_writing, level, native_lang, target_lang, mode
                ),
            ),
        ]
        feedback_text = ""
        for _ in range(_MAX_AGENT_ITERATIONS):
            response = await self._llm.complete(messages, tools=TOOL_SCHEMAS)
            if response.tool_calls:
                tool_results = []
                for tc in response.tool_calls:
                    result = await tools.execute(tc.name, tc.arguments)
                    tool_results.append(f"[{tc.name}]: {result}")
                messages.append(Message(role="assistant", content=response.content or ""))
                messages.append(Message(role="user", content="\n".join(tool_results)))
                if response.content:
                    feedback_text = response.content
                continue
            if response.content:
                feedback_text = response.content
            break
        return feedback_text, tools.created_cards

    async def topic_vocab_lesson(
        self,
        level: str,
        goal: str,
        native_lang: str,
        target_lang: str,
        recent_topics: list[str],
        count: int = DEFAULT_VOCAB_CARD_COUNT,
        force_topic: str | None = None,
    ) -> tuple[str, list[VocabCard]]:
        """Generate goal-aware vocabulary cards for a chosen topic. Returns (topic_name, cards)."""
        tools = AgentTools(self._fetcher, self._anki, target_lang)
        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=build_topic_vocab_prompt(
                    level,
                    goal,
                    target_lang,
                    native_lang,
                    recent_topics,
                    count=count,
                    force_topic=force_topic,
                ),
            ),
        ]
        topic_name = force_topic or "Vocabulary"
        for _ in range(_MAX_AGENT_ITERATIONS):
            response = await self._llm.complete(messages, tools=TOOL_SCHEMAS)
            if not force_topic and response.content and response.content.startswith("Topic:"):
                first_line = response.content.split("\n")[0]
                topic_name = first_line.replace("Topic:", "").strip()
            if response.tool_calls:
                tool_results = []
                for tc in response.tool_calls:
                    result = await tools.execute(tc.name, tc.arguments)
                    tool_results.append(f"[{tc.name}]: {result}")
                messages.append(Message(role="assistant", content=response.content or ""))
                messages.append(Message(role="user", content="\n".join(tool_results)))
                continue
            break
        return topic_name, tools.created_cards[:count]

    async def vocab_only_lesson(
        self,
        level: str,
        native_lang: str,
        target_lang: str,
    ) -> list[VocabCard]:
        """Fetch article and create vocabulary flashcards without Q&A."""
        tools = AgentTools(self._fetcher, self._anki, target_lang)
        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(role="user", content=build_vocab_prompt(level, target_lang, native_lang)),
        ]
        for _ in range(_MAX_AGENT_ITERATIONS):
            response = await self._llm.complete(messages, tools=TOOL_SCHEMAS)
            if response.tool_calls:
                tool_results = []
                for tc in response.tool_calls:
                    result = await tools.execute(tc.name, tc.arguments)
                    tool_results.append(f"[{tc.name}]: {result}")
                messages.append(Message(role="assistant", content=response.content or ""))
                messages.append(Message(role="user", content="\n".join(tool_results)))
                continue
            break
        return tools.created_cards

    async def capture_word(
        self,
        word: str,
        target_lang: str,
        native_lang: str,
        context: str | None = None,
        deck_id: str | None = None,
    ) -> VocabCard:
        """Capture a single word: call LLM to generate card data, create card in backend."""
        import json

        word = word.strip()
        if not word:
            raise WordCaptureError("No word provided")

        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=build_word_capture_prompt(word, target_lang, native_lang, context),
            ),
        ]
        try:
            response = await self._llm.complete(messages, tools=[], temperature=0.3)
        except LLMError as e:
            raise WordCaptureError(f"LLM failed for '{word}': {e}") from e

        raw = (response.content or "").strip()
        if not raw:
            raise WordCaptureError(f"LLM returned empty response for '{word}'")

        # Strip markdown code fences if LLM adds them despite instructions
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise WordCaptureError(f"LLM returned non-JSON for '{word}': {e}") from e

        required = {"word", "word_type", "translation", "example_sentence"}
        missing = required - data.keys()
        if missing:
            raise WordCaptureError(f"LLM response missing fields: {missing}")

        card = VocabCard(
            word=data["word"],
            translation=data["translation"],
            example_sentence=data["example_sentence"],
            word_type=data["word_type"],
            article=data.get("article"),
        )

        try:
            backend_id = await self._anki.create_card(card, deck_id=deck_id)
        except CardBackendError as e:
            raise WordCaptureError(f"Card backend failed for '{word}': {e}") from e
        return VocabCard(
            word=card.word,
            translation=card.translation,
            example_sentence=card.example_sentence,
            word_type=card.word_type,
            article=card.article,
            backend_id=backend_id,
        )

    def _parse_questions(self, text: str) -> list[str]:
        import re

        lines = text.strip().split("\n")
        questions = []
        for line in lines:
            line = line.strip()
            match = re.match(r"^[1-3][.)]\s+(.+)", line)
            if match:
                questions.append(match.group(1).strip())
        return questions[:3]
