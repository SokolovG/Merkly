"""Scheduler controller — called by frontend scheduler jobs.

These endpoints are called by the Telegram bot's APScheduler jobs (frontend/telegram/).
The backend owns the data; the frontend owns the Telegram I/O.
"""

import uuid
from datetime import UTC, datetime, timedelta

from dishka.integrations.litestar import FromDishka, inject
from litestar import Controller, get, post
from litestar.exceptions import NotFoundException
from litestar.params import Parameter

from backend.src.application.agent.core import LessonAgent
from backend.src.domain.enums import Platform
from backend.src.infrastructure.database.repositories.identity_repo import IdentityRepository
from backend.src.infrastructure.database.repositories.profile_repo import ProfileRepository
from backend.src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository
from backend.src.presentation.converters import pooled_card_to_dto, vocab_card_to_dto
from backend.src.presentation.dto.scheduler.requests import MarkReminderSentRequest
from backend.src.presentation.dto.scheduler.responses import (
    DueReminderEntry,
    DueRemindersResponse,
    SchedulerVocabResponse,
)
from backend.src.presentation.responses.base import SuccessResponse


class SchedulerController(Controller):
    path = "/scheduler"

    @get("/reminders/due")
    @inject
    async def get_due_reminders(
        self,
        identity_repo: FromDishka[IdentityRepository],
        platform: str = Parameter(query="platform"),
    ) -> SuccessResponse:
        """Query profiles JOIN contacts WHERE next_reminder_at <= NOW()
        AND platform = {platform} →
        return list of {user_id, platform_user_id, target_lang, reminder_time}.
        Frontend sends the actual Telegram messages, then calls mark-sent."""
        try:
            platform_enum = Platform(platform)
        except ValueError:
            return SuccessResponse(
                data=DueRemindersResponse(reminders=[]), message="No reminders due"
            )

        rows = await identity_repo.get_due_for_platform(platform_enum)
        reminders = [
            DueReminderEntry(
                user_id=str(user_id),
                platform_user_id=platform_user_id,
                target_lang=target_lang,
                reminder_time=reminder_time,
            )
            for user_id, platform_user_id, target_lang, reminder_time in rows
        ]
        return SuccessResponse(
            data=DueRemindersResponse(reminders=reminders), message="Due reminders fetched"
        )

    @post("/reminders/{user_id:str}/mark-sent")
    @inject
    async def mark_reminder_sent(
        self,
        user_id: str,
        data: MarkReminderSentRequest,
        profile_repo: FromDishka[ProfileRepository],
    ) -> None:
        """Compute next_reminder_at from profile.reminder_time + utc_offset →
        persist to DB. Called after frontend confirms the message was sent."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise NotFoundException(detail=f"Invalid user_id: {user_id!r}") from None

        profile = await profile_repo.get_by_id(uid)
        if profile is None:
            raise NotFoundException(detail=f"Profile not found: {user_id}") from None

        # Compute next UTC fire time from local reminder_time + utc_offset
        h, m = map(int, profile.reminder_time.split(":"))
        # Local → UTC: subtract offset (e.g. UTC+2 → local 11:00 = UTC 09:00)
        utc_hour = (h - profile.utc_offset) % 24
        now = datetime.now(UTC)
        candidate = now.replace(hour=utc_hour, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)

        await profile_repo.update_next_reminder_at(uid, candidate)

    @post("/vocab/{user_id:str}")
    @inject
    async def generate_scheduled_vocab(
        self,
        user_id: str,
        profile_repo: FromDishka[ProfileRepository],
        vocab_repo: FromDishka[VocabPoolRepository],
        agent: FromDishka[LessonAgent],
    ) -> SuccessResponse:
        """Serve vocab cards from pool for the nightly vocab scheduler job →
        mark shown → return cards for frontend to send via Telegram."""
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            raise NotFoundException(detail=f"Invalid user_id: {user_id!r}") from None

        profile = await profile_repo.get_by_id(uid)
        if profile is None:
            raise NotFoundException(detail=f"Profile not found: {user_id}") from None

        card_count = profile.vocab_card_count
        pool_cards = await vocab_repo.get_pool_cards(
            profile.id, str(profile.target_lang), card_count
        )

        if pool_cards:
            await vocab_repo.mark_shown(profile.id, [c.id for c in pool_cards])
            return SuccessResponse(
                data=SchedulerVocabResponse(cards=[pooled_card_to_dto(c) for c in pool_cards]),
                message="Scheduled vocab served from pool",
            )

        # Pool empty — generate live (best-effort for scheduler)
        _, vocab_cards = await agent.topic_vocab_lesson(
            level=profile.level,
            goal=str(profile.goal),
            native_lang=str(profile.native_lang),
            target_lang=str(profile.target_lang),
            recent_topics=[],
            count=card_count,
            force_topic=None,
        )
        return SuccessResponse(
            data=SchedulerVocabResponse(cards=[vocab_card_to_dto(c) for c in vocab_cards]),
            message="Scheduled vocab generated",
        )
