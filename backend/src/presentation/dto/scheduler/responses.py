import msgspec

from backend.src.presentation.dto.shared.responses import CardDTO


class DueReminderEntry(msgspec.Struct):
    """One user due for a reminder."""

    user_id: str  # UUID as str
    platform_user_id: str
    target_lang: str
    reminder_time: str  # "HH:MM" local


class DueRemindersResponse(msgspec.Struct):
    """Response for GET /scheduler/reminders/due."""

    reminders: list[DueReminderEntry]


class SchedulerVocabResponse(msgspec.Struct):
    """Response for POST /scheduler/vocab/{user_id}."""

    cards: list[CardDTO]
