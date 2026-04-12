import logging

from src.application.agent.core import LessonAgent
from src.domain.constants import POOL_FILL_SIZE, POOL_RECENT_HINT, POOL_THRESHOLD
from src.domain.entities import UserProfile
from src.domain.ports.vocab_pool_repo import IVocabPoolRepository

logger = logging.getLogger(__name__)


class VocabRefillService:
    def __init__(self, agent: LessonAgent, repo: IVocabPoolRepository) -> None:
        self._agent = agent
        self._repo = repo

    async def refill_if_needed(self, profile: UserProfile) -> bool:
        """Refill pool if below threshold. Returns True if refill was triggered."""
        count = await self._repo.pool_count(profile.id, str(profile.target_lang))
        if count >= POOL_THRESHOLD:
            return False
        await self._refill(profile)
        return True

    async def _refill(self, profile: UserProfile) -> None:
        hint_words = await self._repo.get_history_words(
            profile.id,
            str(profile.target_lang),
            limit=POOL_RECENT_HINT,
        )
        logger.info(
            "Refilling vocab pool for user=%s lang=%s hint_count=%d",
            profile.id,
            profile.target_lang,
            len(hint_words),
        )
        _, cards = await self._agent.topic_vocab_lesson(
            level=profile.level,
            goal=str(profile.goal),
            native_lang=str(profile.native_lang),
            target_lang=str(profile.target_lang),
            recent_topics=hint_words,
            count=POOL_FILL_SIZE,
            pool_mode=True,
        )
        await self._repo.add_to_pool(profile.id, cards, str(profile.target_lang))
        logger.info(
            "Pool refill complete for user=%s lang=%s cards_added=%d",
            profile.id,
            profile.target_lang,
            len(cards),
        )
