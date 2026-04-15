from datetime import UTC, datetime, timedelta


def compute_next_reminder_at(reminder_time: str, utc_offset: int) -> datetime:
    """Return next UTC datetime when this reminder should fire.

    reminder_time: 'HH:MM' in user's local time
    utc_offset: hours to add to UTC to get user's local time
    """
    now_utc = datetime.now(UTC)
    h, m = map(int, reminder_time.split(":"))
    # Today at reminder_time expressed in UTC
    # UTC = local_time - utc_offset
    today_midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    candidate = today_midnight_utc.replace(hour=h, minute=m) - timedelta(hours=utc_offset)
    if candidate <= now_utc:
        candidate += timedelta(days=1)
    return candidate
