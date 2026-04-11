from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import PooledVocabCard, VocabCard
from src.domain.enums import WordType
from src.domain.ports.vocab_pool_repo import IVocabPoolRepository
from src.infrastructure.database.models.profile_model import ProfileModel
from src.infrastructure.database.models.vocab_history_model import VocabHistoryModel
from src.infrastructure.database.models.vocab_pool_model import VocabPoolModel


class VocabPoolRepository(IVocabPoolRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def _resolve_profile_id(self, telegram_id: int) -> int:
        result = await self._db.execute(
            select(ProfileModel.id).where(ProfileModel.telegram_id == telegram_id)
        )
        return result.scalar_one()

    async def pool_count(self, user_id: int, target_lang: str) -> int:
        profile_id = await self._resolve_profile_id(user_id)
        result = await self._db.execute(
            select(func.count()).where(
                VocabPoolModel.user_id == profile_id,
                VocabPoolModel.target_lang == target_lang,
            )
        )
        return result.scalar_one()

    async def get_pool_cards(
        self, user_id: int, target_lang: str, count: int
    ) -> list[PooledVocabCard]:
        profile_id = await self._resolve_profile_id(user_id)
        result = await self._db.execute(
            select(VocabPoolModel)
            .where(
                VocabPoolModel.user_id == profile_id,
                VocabPoolModel.target_lang == target_lang,
            )
            .order_by(VocabPoolModel.created_at.asc())
            .limit(count)
        )
        rows = result.scalars().all()
        return [
            PooledVocabCard(
                id=row.id,
                word=row.word,
                translation=row.translation,
                example_sentence=row.example_sentence,
                word_type=WordType(row.word_type),
                article=row.article,
                target_lang=row.target_lang,
            )
            for row in rows
        ]

    async def add_to_pool(self, user_id: int, cards: list[VocabCard], target_lang: str) -> None:
        profile_id = await self._resolve_profile_id(user_id)

        # Fetch existing history words for dedup
        result = await self._db.execute(
            select(VocabHistoryModel.word).where(
                VocabHistoryModel.user_id == profile_id,
                VocabHistoryModel.target_lang == target_lang,
            )
        )
        shown_words = {w.lower() for w in result.scalars().all()}

        new_rows = [
            VocabPoolModel(
                user_id=profile_id,
                target_lang=target_lang,
                word=card.word,
                translation=card.translation,
                example_sentence=card.example_sentence,
                word_type=str(card.word_type),
                article=card.article,
            )
            for card in cards
            if card.word.lower() not in shown_words
        ]
        if new_rows:
            self._db.add_all(new_rows)
            await self._db.commit()

    async def mark_shown(self, user_id: int, card_ids: list[int]) -> None:
        profile_id = await self._resolve_profile_id(user_id)

        # Fetch words before deleting
        result = await self._db.execute(
            select(VocabPoolModel.word, VocabPoolModel.target_lang).where(
                VocabPoolModel.id.in_(card_ids)
            )
        )
        shown = result.all()

        # Delete from pool
        await self._db.execute(delete(VocabPoolModel).where(VocabPoolModel.id.in_(card_ids)))

        # Insert into history
        history_rows = [
            VocabHistoryModel(
                user_id=profile_id,
                target_lang=target_lang,
                word=word,
            )
            for word, target_lang in shown
        ]
        if history_rows:
            self._db.add_all(history_rows)

        await self._db.commit()

    async def clear_pool(self, user_id: int, target_lang: str) -> int:
        profile_id = await self._resolve_profile_id(user_id)
        count_result = await self._db.execute(
            select(func.count()).where(
                VocabPoolModel.user_id == profile_id,
                VocabPoolModel.target_lang == target_lang,
            )
        )
        count: int = count_result.scalar_one()
        await self._db.execute(
            delete(VocabPoolModel).where(
                VocabPoolModel.user_id == profile_id,
                VocabPoolModel.target_lang == target_lang,
            )
        )
        await self._db.commit()
        return count

    async def get_history_words(
        self, user_id: int, target_lang: str, limit: int, oldest_first: bool = False
    ) -> list[str]:
        profile_id = await self._resolve_profile_id(user_id)
        order = (
            VocabHistoryModel.created_at.asc()
            if oldest_first
            else VocabHistoryModel.created_at.desc()
        )
        result = await self._db.execute(
            select(VocabHistoryModel.word)
            .where(
                VocabHistoryModel.user_id == profile_id,
                VocabHistoryModel.target_lang == target_lang,
            )
            .order_by(order)
            .limit(limit)
        )
        return list(result.scalars().all())
