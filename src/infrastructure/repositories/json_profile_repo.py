import asyncio
from pathlib import Path

import msgspec

from src.domain.entities import UserProfile


class JsonProfileRepository:
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir / "profiles"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, telegram_id: int) -> Path:
        return self._dir / f"{telegram_id}.json"

    async def get(self, telegram_id: int) -> UserProfile | None:
        path = self._path(telegram_id)
        if not path.exists():
            return None
        data = await asyncio.to_thread(path.read_bytes)
        return msgspec.json.decode(data, type=UserProfile)

    async def save(self, profile: UserProfile) -> None:
        data = msgspec.json.encode(profile)
        await asyncio.to_thread(self._path(profile.telegram_id).write_bytes, data)

    async def all_with_reminders(self) -> list[UserProfile]:
        profiles = []
        for path in self._dir.glob("*.json"):
            data = await asyncio.to_thread(path.read_bytes)
            profile = msgspec.json.decode(data, type=UserProfile)
            if profile.reminder_enabled:
                profiles.append(profile)
        return profiles
