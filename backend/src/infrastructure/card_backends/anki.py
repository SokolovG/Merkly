import httpx
import structlog

from backend.src.domain.entities import VocabCard
from backend.src.domain.ports.card_gateway import ICardGateway
from backend.src.infrastructure.exceptions import CardBackendError

logger = structlog.get_logger(__name__)


class AnkiClient(ICardGateway):
    def __init__(self, connect_url: str, deck: str = "Language::Daily") -> None:
        self._url = connect_url
        self._deck = deck
        self._client = httpx.AsyncClient(timeout=5)

    async def is_available(self) -> bool:
        try:
            resp = await self._client.post(
                self._url,
                json={"action": "version", "version": 6},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def create_card(self, card: VocabCard, deck_id: str | None = None) -> str | None:
        front = self._build_front(card)
        back = self._build_back(card)

        payload = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": deck_id or self._deck,
                    "modelName": "Basic",
                    "fields": {"Front": front, "Back": back},
                    "options": {"allowDuplicate": False},
                    "tags": ["lang-tutor", card.word_type],
                }
            },
        }
        try:
            logger.info("card_create_attempt", integration="anki", deck=deck_id or self._deck)
            resp = await self._client.post(self._url, json=payload)
            result = resp.json()
            if result.get("error"):
                raise CardBackendError(f"Anki error: {result['error']}")
            note_id = result.get("result")
            if note_id:
                logger.info("card_created", integration="anki", card_id=str(note_id))
            return str(note_id) if note_id else None
        except CardBackendError:
            raise
        except Exception as exc:
            logger.warning("card_create_failed", integration="anki", error=str(exc))
            raise CardBackendError(f"Anki request failed: {exc}") from exc

    async def create_deck(self, name: str) -> str:
        payload = {
            "action": "createDeck",
            "version": 6,
            "params": {"deck": name},
        }
        try:
            resp = await self._client.post(self._url, json=payload)
            result = resp.json()
            if result.get("error"):
                raise CardBackendError(f"Anki create deck error: {result['error']}")
            return name  # Anki identifies decks by name
        except CardBackendError:
            raise
        except Exception as exc:
            raise CardBackendError(f"Anki create deck failed: {exc}") from exc

    async def list_decks(self) -> list[tuple[str, str]]:
        payload = {"action": "deckNames", "version": 6}
        try:
            resp = await self._client.post(self._url, json=payload)
            result = resp.json()
            if result.get("error"):
                raise CardBackendError(f"Anki list decks error: {result['error']}")
            deck_names: list[str] = result.get("result") or []
            return [(name, name) for name in deck_names]
        except CardBackendError:
            raise
        except Exception as exc:
            raise CardBackendError(f"Anki list decks failed: {exc}") from exc

    async def delete_card(self, card_id: str) -> bool:
        payload = {
            "action": "deleteNotes",
            "version": 6,
            "params": {"notes": [int(card_id)]},
        }
        try:
            resp = await self._client.post(self._url, json=payload)
            if resp.json().get("error"):
                raise CardBackendError(f"Anki delete error: {resp.json()['error']}")
            return True
        except CardBackendError:
            raise
        except Exception as exc:
            raise CardBackendError(f"Anki delete failed: {exc}") from exc

    def _build_front(self, card: VocabCard) -> str:
        if card.word_type == "noun" and card.article:
            return f"{card.article} {card.word}"
        return card.word

    def _build_back(self, card: VocabCard) -> str:
        lines = [card.translation, "", f"<i>{card.example_sentence}</i>"]
        if card.grammar_note:
            lines += ["", f"<small>{card.grammar_note}</small>"]
        return "<br>".join(lines)
