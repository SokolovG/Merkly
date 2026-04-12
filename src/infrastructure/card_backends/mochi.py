import httpx
import structlog

from src.domain.entities import VocabCard
from src.domain.ports.card_gateway import ICardGateway
from src.infrastructure.exceptions import CardBackendError

logger = structlog.get_logger(__name__)


class MochiClient(ICardGateway):
    """Mochi spaced-repetition card gateway.

    Auth: Basic auth with API key as username, empty password.
    Docs: https://mochi.cards/docs/api
    """

    def __init__(
        self, api_key: str, deck_id: str, base_url: str = "https://app.mochi.cards/api"
    ) -> None:
        self._deck_id = deck_id
        self._back_field_id: str | None = None  # discovered lazily from the deck template
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=(api_key, ""),
            timeout=10,
        )

    async def is_available(self) -> bool:
        try:
            resp = await self._client.get("/decks/")
            return resp.status_code == 200
        except Exception:
            return False

    async def _get_back_field_id(self) -> str | None:
        """Discover the 'Back' field ID from the deck's template (cached after first call)."""
        if self._back_field_id is not None:
            return self._back_field_id
        try:
            deck_resp = await self._client.get(f"/decks/{self._deck_id}")
            template_id = deck_resp.json().get("template-id")
            if not template_id:
                return None
            tmpl_resp = await self._client.get(f"/templates/{template_id}")
            fields: dict = tmpl_resp.json().get("fields", {})
            back_id = next((fid for fid in fields if fid != "name"), None)
            if back_id:
                self._back_field_id = back_id
            return self._back_field_id
        except Exception:
            return None

    async def create_card(self, card: VocabCard, deck_id: str | None = None) -> str | None:
        front = self._build_front(card)
        back = self._build_back(card)
        back_field_id = await self._get_back_field_id()

        fields: dict = {"name": {"id": "name", "value": front}}
        if back_field_id:
            fields[back_field_id] = {"id": back_field_id, "value": back}

        payload = {
            "deck-id": deck_id or self._deck_id,
            "content": f"## {front}\n---\n{back}",
            "fields": fields,
        }
        try:
            logger.info("card_create_attempt", integration="mochi", deck=deck_id or self._deck_id)
            resp = await self._client.post("/cards/", json=payload)
            if resp.status_code in (200, 201):
                card_id = resp.json().get("id")
                if card_id:
                    logger.info("card_created", integration="mochi", card_id=card_id)
                return card_id
            raise CardBackendError(f"Mochi {resp.status_code}: {resp.text[:200]}")
        except CardBackendError:
            raise
        except Exception as exc:
            logger.warning("card_create_failed", integration="mochi", error=str(exc))
            raise CardBackendError(f"Mochi request failed: {exc}") from exc

    async def create_deck(self, name: str) -> str:
        try:
            resp = await self._client.post("/decks/", json={"name": name})
            if resp.status_code not in (200, 201):
                raise CardBackendError(f"Mochi create deck {resp.status_code}: {resp.text[:200]}")
            deck_id = resp.json().get("id")
            if not deck_id:
                raise CardBackendError("Mochi create deck returned no id")
            return deck_id
        except CardBackendError:
            raise
        except Exception as exc:
            raise CardBackendError(f"Mochi create deck failed: {exc}") from exc

    async def list_decks(self) -> list[tuple[str, str]]:
        try:
            resp = await self._client.get("/decks/")
            if resp.status_code != 200:
                raise CardBackendError(f"Mochi list decks {resp.status_code}: {resp.text[:200]}")
            docs = resp.json().get("docs", [])
            seen: set[str] = set()
            result = []
            for d in docs:
                if "id" in d and "name" in d and d["id"] not in seen and not d.get("trashed?"):
                    seen.add(d["id"])
                    result.append((d["name"], d["id"]))
            return result
        except CardBackendError:
            raise
        except Exception as exc:
            raise CardBackendError(f"Mochi list decks failed: {exc}") from exc

    async def delete_card(self, card_id: str) -> bool:
        try:
            resp = await self._client.delete(f"/cards/{card_id}")
            if resp.status_code not in (200, 204):
                raise CardBackendError(f"Mochi delete {resp.status_code}: {card_id}")
            return True
        except CardBackendError:
            raise
        except Exception as exc:
            raise CardBackendError(f"Mochi delete failed: {exc}") from exc

    def _build_front(self, card: VocabCard) -> str:
        if card.word_type == "noun" and card.article:
            return f"{card.article} {card.word}"
        return card.word

    def _build_back(self, card: VocabCard) -> str:
        lines = [
            f"**{card.translation}**",
            "",
            f"*{card.example_sentence}*",
        ]
        if card.grammar_note:
            lines += ["", card.grammar_note]
        if card.word_type:
            lines.append(f"\n`{card.word_type}`")
        return "\n".join(lines)
