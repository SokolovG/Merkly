import httpx

from src.domain.entities import VocabCard
from src.domain.ports.card_gateway import ICardGateway

_BASE_URL = "https://app.mochi.cards/api"


class MochiClient:
    """Mochi spaced-repetition card gateway.

    Auth: Basic auth with API key as username, empty password.
    Docs: https://mochi.cards/docs/api
    """

    def __init__(self, api_key: str, deck_id: str) -> None:
        self._deck_id = deck_id
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

    async def create_card(self, card: VocabCard) -> str | None:
        content = self._build_content(card)
        payload = {
            "deck-id": self._deck_id,
            "content": content,
            "fields": {
                "name": {"id": "name", "value": self._build_front(card)},
            },
        }
        try:
            resp = await self._client.post("/cards/", json=payload)
            if resp.status_code in (200, 201):
                return resp.json().get("id")
            return None
        except Exception:
            return None

    async def delete_card(self, card_id: str) -> bool:
        try:
            resp = await self._client.delete(f"/cards/{card_id}")
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def _build_front(self, card: VocabCard) -> str:
        if card.word_type == "noun" and card.article:
            return f"{card.article} {card.word}"
        return card.word

    def _build_content(self, card: VocabCard) -> str:
        front = self._build_front(card)
        lines = [
            f"# {front}",
            "",
            f"**{card.translation}**",
            "",
            f"*{card.example_sentence}*",
        ]
        if card.word_type:
            lines.append(f"\n`{card.word_type}`")
        return "\n".join(lines)


_: ICardGateway = MochiClient.__new__(MochiClient)
