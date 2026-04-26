import re

import structlog

from backend.src.application.agent.prompts import (
    build_review_prompt,
    build_system_prompt,
    lang_name,
)
from backend.src.application.agent.tools import READING_TOOL_SCHEMAS, TOOL_SCHEMAS, AgentTools
from backend.src.domain.constants import DEFAULT_QUESTION_COUNT
from backend.src.domain.entities import VocabCard
from backend.src.domain.ports.article_fetcher import IArticleFetcher
from backend.src.domain.ports.card_gateway import ICardGateway
from backend.src.domain.ports.llm_gateway import ILLMGateway, Message

logger = structlog.get_logger(__name__)

_MAX_AGENT_ITERATIONS = 10


class ReadingAgent:
    """Handles reading lesson preparation and answer review."""

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

    def _parse_questions(self, text: str, count: int = 3) -> list[str]:
        lines = text.strip().split("\n")
        questions = []
        for line in lines:
            line = line.strip()
            match = re.match(r"^\d+[.)]\s+(.+)", line)
            if match:
                questions.append(match.group(1).strip())
        return questions[:count]
