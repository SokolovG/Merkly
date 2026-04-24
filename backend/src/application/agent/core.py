import json
from dataclasses import dataclass

import structlog

from backend.src.application.agent.prompts import (
    build_review_prompt,
    build_standalone_writing_task_prompt,
    build_system_prompt,
    build_topic_vocab_prompt,
    build_vocab_prompt,
    build_word_capture_prompt,
    build_writing_review_prompt,
    build_writing_task_prompt,
    build_writing_themes_prompt,
    lang_name,
    strip_article_from_word,
)
from backend.src.application.agent.tools import READING_TOOL_SCHEMAS, TOOL_SCHEMAS, AgentTools
from backend.src.domain.constants import DEFAULT_QUESTION_COUNT
from backend.src.domain.entities import DEFAULT_VOCAB_CARD_COUNT, VocabCard
from backend.src.domain.exceptions import WordCaptureError
from backend.src.domain.ports.article_fetcher import IArticleFetcher
from backend.src.domain.ports.card_gateway import ICardGateway
from backend.src.domain.ports.llm_gateway import ILLMGateway, Message
from backend.src.infrastructure.exceptions import CardBackendError, LLMError


@dataclass
class LessonResult:
    article_title: str
    article_url: str
    article_text: str
    questions: list[str]
    feedback: str
    cards_created: list[VocabCard]


logger = structlog.get_logger(__name__)

_MAX_AGENT_ITERATIONS = 10


class LessonAgent:
    def __init__(
        self,
        llm: ILLMGateway,
        fetcher: IArticleFetcher,
        card_gateway: ICardGateway,
    ) -> None:
        self._llm = llm
        self._fetcher = fetcher
        self._card_gateway = card_gateway

    async def prepare_reading_lesson(
        self,
        level: str,
        goal: str,
        native_lang: str,
        target_lang: str,
        recent_topics: list[str],
        question_count: int = DEFAULT_QUESTION_COUNT,
    ) -> tuple[str, str, str, list[str]]:
        """Fetch article and generate questions. Returns (title, url, text, questions)."""
        logger.info("lesson_start", level=level, target_lang=target_lang)
        tools = AgentTools(self._fetcher, self._card_gateway, target_lang)

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
                    f"2. Return EXACTLY {question_count} comprehension questions IN "
                    f"{lang_name(target_lang).upper()} (numbered 1. 2. etc.)\n"
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
                questions = self._parse_questions(response.content, question_count)
                article = tools.fetched_article
                if article and questions:
                    logger.info("article_fetched", url=article.url)
                    logger.info("questions_generated", count=len(questions))
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

        logger.info("review_complete", has_feedback=bool(feedback_text))
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

    async def generate_writing_themes(
        self,
        target_lang: str,
        native_lang: str,
        level: str,
        count: int = 5,
    ) -> list[str]:
        """Return a list of writing topic strings for the given language/level."""
        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=build_writing_themes_prompt(target_lang, native_lang, level, count),
            ),
        ]
        response = await self._llm.complete(messages, tools=[])
        raw = (response.content or "").strip()

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Drop first line (```json or ```) and last line (```)
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()

        try:
            themes: list[str] = json.loads(raw)
            return [str(t) for t in themes[:count]]
        except (json.JSONDecodeError, TypeError):
            # LLM didn't return valid JSON — extract lines as fallback
            lines = [
                ln.strip().strip('",').strip("'").strip("-").strip() for ln in raw.splitlines()
            ]
            return [ln for ln in lines if ln and not ln.startswith("[") and not ln.startswith("]")][
                :count
            ]

    async def generate_standalone_writing_task(
        self,
        theme: str,
        target_lang: str,
        level: str,
        mode: str = "article",
    ) -> str:
        """Generate a writing task for a theme with no article context."""
        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=build_standalone_writing_task_prompt(theme, target_lang, level, mode),
            ),
        ]
        response = await self._llm.complete(messages, tools=[])
        return response.content or f"Write a 200-word text about: {theme}"

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
        tools = AgentTools(self._fetcher, self._card_gateway, target_lang)
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
        logger.info("writing_review_complete", cards_created=len(tools.created_cards))
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
        pool_mode: bool = False,
    ) -> tuple[str, list[VocabCard]]:
        """Generate goal-aware vocabulary cards for a chosen topic. Returns (topic_name, cards).

        pool_mode=True: collect cards only, skip backend (Anki/Mochi) — used by VocabRefillService.
        """
        tools = AgentTools(self._fetcher, self._card_gateway, target_lang, pool_mode=pool_mode)
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
        logger.info("vocab_generated", count=len(tools.created_cards[:count]), topic=topic_name)
        return topic_name, tools.created_cards[:count]

    async def vocab_only_lesson(
        self,
        level: str,
        native_lang: str,
        target_lang: str,
    ) -> list[VocabCard]:
        """Fetch article and create vocabulary flashcards without Q&A."""
        tools = AgentTools(self._fetcher, self._card_gateway, target_lang)
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

        article = data.get("article") or None
        card = VocabCard(
            word=strip_article_from_word(data["word"], article),
            translation=data["translation"],
            example_sentence=data["example_sentence"],
            word_type=data["word_type"],
            article=article,
            grammar_note=data.get("grammar_note") or None,
        )

        try:
            backend_id = await self._card_gateway.create_card(card, deck_id=deck_id)
        except CardBackendError as e:
            raise WordCaptureError(f"Card backend failed for '{word}': {e}") from e
        logger.info("word_captured", word_type=card.word_type)
        return VocabCard(
            word=card.word,
            translation=card.translation,
            example_sentence=card.example_sentence,
            word_type=card.word_type,
            article=card.article,
            grammar_note=card.grammar_note,
            backend_id=backend_id,
        )

    def _parse_questions(self, text: str, count: int = 3) -> list[str]:
        import re

        lines = text.strip().split("\n")
        questions = []
        for line in lines:
            line = line.strip()
            match = re.match(r"^\d+[.)]\s+(.+)", line)
            if match:
                questions.append(match.group(1).strip())
        return questions[:count]
