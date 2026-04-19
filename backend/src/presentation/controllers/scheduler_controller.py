"""Scheduler controller — called by frontend scheduler jobs.

These endpoints are called by the Telegram bot's APScheduler jobs (frontend/telegram/).
The backend owns the data; the frontend owns the Telegram I/O.
"""

from litestar import Controller, get, post
from litestar.params import Parameter

from backend.src.presentation.dto.scheduler.requests import MarkReminderSentRequest
from backend.src.presentation.responses.base import SuccessResponse


class SchedulerController(Controller):
    path = "/scheduler"

    @get("/reminders/due")
    async def get_due_reminders(
        self,
        platform: str = Parameter(query="platform"),
    ) -> SuccessResponse:
        """Query profiles JOIN contacts WHERE next_reminder_at <= NOW()
        AND platform = {platform} →
        return list of {user_id, platform_user_id, target_lang, reminder_time}.
        Frontend sends the actual Telegram messages, then calls mark-sent."""
        raise NotImplementedError

    @post("/reminders/{user_id:str}/mark-sent")
    async def mark_reminder_sent(self, user_id: str, data: MarkReminderSentRequest) -> None:
        """Compute next_reminder_at from profile.reminder_time + utc_offset →
        persist to DB. Called after frontend confirms the message was sent."""
        raise NotImplementedError

    @post("/vocab/{user_id:str}")
    async def generate_scheduled_vocab(self, user_id: str) -> SuccessResponse:
        """Serve vocab cards from pool for the nightly vocab scheduler job →
        mark shown → return cards for frontend to send via Telegram."""
        raise NotImplementedError
