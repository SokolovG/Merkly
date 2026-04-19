"""Vocab controller — card generation, word capture, repeat."""

from litestar import Controller, get, post
from litestar.params import Parameter

from backend.src.presentation.dto.vocab.requests import (
    CaptureWordRequest,
    RegenerateWordRequest,
)
from backend.src.presentation.responses.base import SuccessResponse


class VocabController(Controller):
    path = "/vocab"

    @get("")
    async def generate_vocab(
        self,
        user_id: str = Parameter(query="user_id"),
        count: int | None = Parameter(query="count", default=None),
        topic: str | None = Parameter(query="topic", default=None),
    ) -> SuccessResponse:
        """Serve vocab cards from pool (refill if needed) →
        return topic + cards. count defaults to profile.vocab_card_count."""
        raise NotImplementedError

    @get("/repeat")
    async def repeat_vocab(
        self,
        user_id: str = Parameter(query="user_id"),
        count: int | None = Parameter(query="count", default=None),
    ) -> SuccessResponse:
        """Return oldest-first cards from vocab_history.
        No LLM call. count defaults to profile.vocab_card_count."""
        raise NotImplementedError

    @post("/word")
    async def capture_word(self, data: CaptureWordRequest) -> SuccessResponse:
        """Run +word capture flow: LLM generates card →
        save to Anki/Mochi → return card + pool_card_id for possible regeneration."""
        raise NotImplementedError

    @post("/word/regenerate")
    async def regenerate_word(self, data: RegenerateWordRequest) -> SuccessResponse:
        """Re-run word capture with explicit context →
        delete old card from backend, create new one → return updated card."""
        raise NotImplementedError
