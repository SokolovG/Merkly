import json

import structlog

from backend.src.application.agent.prompts import (
    build_system_prompt,
    build_topic_vocab_prompt,
    build_vocab_prompt,
    build_word_capture_prompt,
    strip_article_from_word,
)
from backend.src.application.agent.tools import TOOL_SCHEMAS, AgentTools
from backend.src.domain.entities import DEFAULT_VOCAB_CARD_COUNT, VocabCard
from backend.src.domain.exceptions import WordCaptureError
from backend.src.domain.ports.article_fetcher import IArticleFetcher
from backend.src.domain.ports.card_gateway import ICardGateway
from backend.src.domain.ports.llm_gateway import ILLMGateway, Message
from backend.src.infrastructure.exceptions import CardBackendError, LLMError

logger = structlog.get_logger(__name__)

_MAX_AGENT_ITERATIONS = 10


class VocabAgent:
    """Handles vocabulary generation and word capture."""

    def __init__(
        self,
        llm: ILLMGateway,
        fetcher: IArticleFetcher,
        card_gateway: ICardGateway,
    ) -> None:
        self._llm = llm
        self._fetcher = fetcher
        self._card_gateway = card_gateway

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
