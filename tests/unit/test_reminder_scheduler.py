"""Tests for the reminder scheduler compute_next_reminder_at function."""

from datetime import UTC, datetime

from src.domain.utils import compute_next_reminder_at


class TestComputeNextReminderAt:
    """Test compute_next_reminder_at() computes correct future UTC timestamps."""

    def test_always_returns_future(self):
        """Result is always strictly greater than now_utc."""
        now = datetime.now(UTC)
        for hour in (0, 3, 6, 9, 12, 15, 18, 21, 23):
            for offset in (-5, 0, 3):
                result = compute_next_reminder_at(f"{hour:02d}:00", offset)
                assert result > now, f"Failed for {hour:02d}:00, offset={offset}"

    def test_utc_offset_shifts_time(self):
        """UTC offset correctly shifts the target time."""
        # Reminder at 14:00 local, UTC+3 → should be 11:00 UTC
        result = compute_next_reminder_at("14:00", 3)
        expected_hour = (14 - 3) % 24
        assert result.hour == expected_hour

    def test_negative_utc_offset(self):
        """Negative UTC offset (west of UTC) works correctly."""
        # Reminder at 09:00 local, UTC-5 → should be 14:00 UTC
        result = compute_next_reminder_at("09:00", -5)
        expected_hour = (9 - (-5)) % 24
        assert result.hour == expected_hour

    def test_midnight_reminder(self):
        """Reminder at 00:00 works correctly."""
        result = compute_next_reminder_at("00:00", 0)
        assert result > datetime.now(UTC)

    def test_same_time_as_now_returns_tomorrow(self):
        """If reminder time equals now (edge case), returns tomorrow."""
        result = compute_next_reminder_at("11:00", 0)
        assert result > datetime.now(UTC)

    def test_minutes_preserved(self):
        """Minutes from reminder_time are preserved."""
        result = compute_next_reminder_at("14:30", 0)
        assert result.minute == 30
