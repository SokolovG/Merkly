import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import Session, VocabCard
from src.domain.enums import WordType
from src.domain.ports.session_repo import ISessionRepository
from src.infrastructure.database.models.profile_model import ProfileModel
from src.infrastructure.database.models.session_model import SessionModel


class SessionRepository(ISessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    def _to_domain(self, row: SessionModel, messenger_id: int) -> Session:
        cards = [
            VocabCard(
                word=d["word"],
                translation=d["translation"],
                example_sentence=d["example_sentence"],
                word_type=WordType(d["word_type"]),
                article=d.get("article"),
                backend_id=d.get("backend_id"),
            )
            for d in (row.cards_created or [])
        ]
        return Session(
            session_id=row.session_id,
            user_id=messenger_id,
            date=row.created_at.strftime("%Y-%m-%d") if row.created_at else "",
            article_url=row.article_url,
            article_title=row.article_title,
            article_text=row.article_text,
            questions=list(row.questions or []),
            user_answers=list(row.user_answers or []),
            feedback=row.feedback,
            cards_created=cards,
            duration_seconds=row.duration_seconds,
        )

    def _to_values(self, session: Session, user_id: uuid.UUID) -> dict:
        return {
            "session_id": session.session_id,
            "user_id": user_id,
            "article_url": session.article_url,
            "article_title": session.article_title,
            "article_text": session.article_text,
            "questions": list(session.questions),
            "user_answers": list(session.user_answers),
            "feedback": session.feedback,
            "cards_created": [
                {
                    "word": c.word,
                    "translation": c.translation,
                    "example_sentence": c.example_sentence,
                    "word_type": str(c.word_type),
                    "article": c.article,
                    "backend_id": c.backend_id,
                }
                for c in session.cards_created
            ],
            "duration_seconds": session.duration_seconds,
        }

    async def save(self, session: Session, user_id: uuid.UUID) -> None:
        values = self._to_values(session, user_id)
        stmt = pg_insert(SessionModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["session_id"],
            set_={k: stmt.excluded[k] for k in values if k != "session_id"},
        )
        await self._db.execute(stmt)
        await self._db.commit()

    async def get_recent(self, user_id: uuid.UUID, limit: int = 3) -> list[Session]:
        result = await self._db.execute(
            select(SessionModel, ProfileModel.messenger_id)
            .join(ProfileModel, SessionModel.user_id == ProfileModel.id)
            .where(ProfileModel.id == user_id)
            .order_by(SessionModel.created_at.desc())
            .limit(limit)
        )
        rows = result.all()
        return [self._to_domain(row, mid) for row, mid in rows]
