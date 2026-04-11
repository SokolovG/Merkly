import logging

from src.application.agent.prompts import strip_article_from_word
from src.domain.entities import VocabCard
from src.domain.ports.article_fetcher import Article, IArticleFetcher
from src.domain.ports.card_gateway import ICardGateway

logger = logging.getLogger(__name__)

READING_TOOL_SCHEMAS: list[dict] = []

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_article",
            "description": (
                "Fetch a news article from an RSS feed. "
                "If one source fails, call again with the next source_url from the list provided. "
                "Keep trying until an article is fetched."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "The CEFR level of the student (e.g. A1, B1, B1+, B2-, C1)",
                    },
                    "source_url": {
                        "type": "string",
                        "description": (
                            "RSS feed URL to fetch from. "
                            "Use the sources listed in your instructions."
                        ),
                    },
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_flash_card",
            "description": "Create a flashcard for a vocabulary word from the target language",
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {"type": "string", "description": "The word in the target language"},
                    "translation": {
                        "type": "string",
                        "description": "Translation in the student's native language",
                    },
                    "example_sentence": {
                        "type": "string",
                        "description": "An example sentence using the word in the target language",
                    },
                    "word_type": {
                        "type": "string",
                        "enum": ["noun", "verb", "adjective", "phrase"],
                    },
                    "article": {
                        "type": "string",
                        "description": (
                            "Grammatical article for nouns "
                            "(language-dependent, e.g. der/die/das, el/la, le/la)"
                        ),
                    },
                },
                "required": ["word", "translation", "example_sentence", "word_type"],
            },
        },
    },
]


class AgentTools:
    def __init__(
        self,
        fetcher: IArticleFetcher,
        anki: ICardGateway,
        target_lang: str,
        pool_mode: bool = False,
    ) -> None:
        self._fetcher = fetcher
        self._anki = anki
        self._target_lang = target_lang
        self._pool_mode = pool_mode  # True = collect cards only, skip backend
        self.fetched_article: Article | None = None
        self.created_cards: list[VocabCard] = []
        self._created_words: set[str] = set()

    async def execute(self, name: str, arguments: dict) -> str:
        logger.info("→ tool call: %s  args=%s", name, arguments)
        result = await self._dispatch(name, arguments)
        logger.info("← tool result: %s  → %s", name, result[:50] if len(result) > 200 else result)
        return result

    async def _dispatch(self, name: str, arguments: dict) -> str:
        if name == "fetch_article":
            return await self._fetch_article(arguments["level"], arguments.get("source_url"))
        if name == "create_flash_card":
            return await self.create_flash_card(arguments)
        return f"Unknown tool: {name}"

    async def _fetch_article(self, level: str, source_url: str | None = None) -> str:
        try:
            article = await self._fetcher.fetch(level, self._target_lang, source_url)
            self.fetched_article = article
            return f"Title: {article.title}\n\nText:\n{article.text}"
        except Exception as e:
            return f"ERROR fetching from {source_url or 'default'}: {e}. Try the next source_url."

    async def create_flash_card(self, args: dict) -> str:
        article = args.get("article") or None
        word = strip_article_from_word(args["word"], article)
        key = word.lower().strip()
        if key in self._created_words:
            return f"Skipped duplicate: {word}"
        card = VocabCard(
            word=word,
            translation=args["translation"],
            example_sentence=args["example_sentence"],
            word_type=args["word_type"],
            article=article,
        )
        self._created_words.add(key)
        if self._pool_mode:
            # Refill path: store in DB pool only, no backend call
            self.created_cards.append(card)
            return f"Pooled: {card.word} → {card.translation}"
        backend_id = await self._anki.create_card(card)
        card = VocabCard(
            word=card.word,
            translation=card.translation,
            example_sentence=card.example_sentence,
            word_type=card.word_type,
            article=card.article,
            backend_id=backend_id,
        )
        self.created_cards.append(card)
        if backend_id:
            return f"Card created: {card.word} → {card.translation}"
        return f"Card saved locally: {card.word} → {card.translation} (backend not connected)"
