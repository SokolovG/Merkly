from typing import Protocol

from src.domain.entities import VocabCard


class ICardGateway(Protocol):
    async def create_card(self, card: VocabCard) -> str | None:
        """Create card. Returns backend ID on success, None on failure."""
        ...

    async def delete_card(self, card_id: str) -> bool: ...
    async def is_available(self) -> bool: ...
