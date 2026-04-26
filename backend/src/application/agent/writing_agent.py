import json

import structlog

from backend.src.application.agent.prompts import (
    build_standalone_writing_task_prompt,
    build_system_prompt,
    build_writing_review_prompt,
    build_writing_task_prompt,
    build_writing_themes_prompt,
)
from backend.src.application.agent.tools import TOOL_SCHEMAS, AgentTools
from backend.src.domain.entities import VocabCard
from backend.src.domain.ports.article_fetcher import IArticleFetcher
from backend.src.domain.ports.card_gateway import ICardGateway
from backend.src.domain.ports.llm_gateway import ILLMGateway, Message

logger = structlog.get_logger(__name__)

_MAX_AGENT_ITERATIONS = 10


class WritingAgent:
    """Handles writing task generation, theme generation, and writing review."""

    def __init__(
        self,
        llm: ILLMGateway,
        fetcher: IArticleFetcher,
        card_gateway: ICardGateway,
    ) -> None:
        self._llm = llm
        self._fetcher = fetcher
        self._card_gateway = card_gateway

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

        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()

        try:
            themes: list[str] = json.loads(raw)
            return [str(t) for t in themes[:count]]
        except (json.JSONDecodeError, TypeError):
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
