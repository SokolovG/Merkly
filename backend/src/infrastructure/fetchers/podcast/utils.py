def parse_duration(value: str) -> int:
    """Parse an itunes:duration string (HH:MM:SS, MM:SS, or seconds) into seconds."""
    try:
        parts = value.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(value)
    except (ValueError, AttributeError):
        return 0
