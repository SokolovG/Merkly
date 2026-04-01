import logging

import httpx

from src.domain.entities import VocabCard
from src.domain.ports.card_gateway import ICardGateway

_BASE_URL = "https://app.mochi.cards/api"

logger = logging.getLogger(__name__)


class MochiClient:
    """Mochi spaced-repetition card gateway.

    Auth: Basic auth with API key as username, empty password.
    Docs: https://mochi.cards/docs/api
    """

    def __init__(self, api_key: str, deck_id: str) -> None:
        self._deck_id = deck_id
        self._back_field_id: str | None = None  # discovered lazily from the deck template
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
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
            # The back field is the first field that isn't the standard "name" (front) field
            back_id = next((fid for fid in fields if fid != "name"), None)
            if back_id:
                self._back_field_id = back_id
                logger.info("Mochi: discovered back field id=%r template=%r", back_id, template_id)
            return self._back_field_id
        except Exception as exc:
            logger.warning("Mochi: could not discover back field: %s", exc)
            return None

    async def create_card(self, card: VocabCard) -> str | None:
        front = self._build_front(card)
        back = self._build_back(card)
        back_field_id = await self._get_back_field_id()

        fields: dict = {"name": {"id": "name", "value": front}}
        if back_field_id:
            fields[back_field_id] = {"id": back_field_id, "value": back}

        payload = {
            "deck-id": self._deck_id,
            "content": f"## {front}\n---\n{back}",
            "fields": fields,
        }
        try:
            resp = await self._client.post("/cards/", json=payload)
            if resp.status_code in (200, 201):
                card_id = resp.json().get("id")
                logger.info("Mochi: card created word=%r id=%r", card.word, card_id)
                return card_id
            logger.warning(
                "Mochi create_card failed: status=%d body=%r", resp.status_code, resp.text[:300]
            )
            return None
        except Exception as exc:
            logger.error("Mochi create_card exception: %s", exc)
            return None

    async def delete_card(self, card_id: str) -> bool:
        try:
            resp = await self._client.delete(f"/cards/{card_id}")
            return resp.status_code in (200, 204)
        except Exception as exc:
            logger.error("Mochi delete_card exception: id=%r %s", card_id, exc)
            return False

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
        if card.word_type:
            lines.append(f"\n`{card.word_type}`")
        return "\n".join(lines)


_: ICardGateway = MochiClient.__new__(MochiClient)
