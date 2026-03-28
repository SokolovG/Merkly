from dataclasses import dataclass

from src.application.agent.prompts import (
    build_review_prompt,
    build_system_prompt,
    build_topic_vocab_prompt,
    build_vocab_prompt,
    build_writing_review_prompt,
    build_writing_task_prompt,
    lang_name,
)
from src.application.agent.tools import READING_TOOL_SCHEMAS, TOOL_SCHEMAS, AgentTools
from src.domain.entities import VocabCard
from src.domain.ports.article_fetcher import IArticleFetcher
from src.domain.ports.card_gateway import ICardGateway
from src.domain.ports.llm_gateway import ILLMGateway, Message


@dataclass
class LessonResult:
    article_title: str
    article_url: str
    article_text: str
    questions: list[str]
    feedback: str
    cards_created: list[VocabCard]


class LessonAgent:
    MAX_ITERATIONS = 10

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
                    f"2. Return EXACTLY 3 comprehension questions IN {lang_name(target_lang).upper()} "
                    f"(numbered 1. 2. 3.)\n"
                    "Do not do anything else yet."
                ),
            ),
        ]

        for _ in range(self.MAX_ITERATIONS):
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

        for _ in range(self.MAX_ITERATIONS):
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
            Message(role="user", content=build_writing_task_prompt(article_text, target_lang, level, mode)),
        ]
        response = await self._llm.complete(messages, tools=[])
        return response.content or "Write 2–3 sentences about something you found interesting in the article."

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
        for _ in range(self.MAX_ITERATIONS):
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
    ) -> tuple[str, list[VocabCard]]:
        """Generate goal-aware vocabulary cards for a chosen topic. Returns (topic_name, cards)."""
        tools = AgentTools(self._fetcher, self._anki, target_lang)
        messages = [
            Message(role="system", content=build_system_prompt(target_lang)),
            Message(
                role="user",
                content=build_topic_vocab_prompt(level, goal, target_lang, native_lang, recent_topics),
            ),
        ]
        topic_name = "Vocabulary"
        for _ in range(self.MAX_ITERATIONS):
            response = await self._llm.complete(messages, tools=TOOL_SCHEMAS)
            if response.content and response.content.startswith("Topic:"):
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
        return topic_name, tools.created_cards

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
        for _ in range(self.MAX_ITERATIONS):
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
