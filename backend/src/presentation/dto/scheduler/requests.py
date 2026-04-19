import msgspec


class MarkReminderSentRequest(msgspec.Struct):
    """POST /scheduler/reminders/{user_id}/mark-sent"""

    platform: str
