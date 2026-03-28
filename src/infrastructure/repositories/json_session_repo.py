import asyncio
from pathlib import Path

import msgspec

from src.domain.entities import Session


class JsonSessionRepository:
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir / "sessions"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: int) -> Path:
        d = self._dir / str(user_id)
        d.mkdir(exist_ok=True)
        return d

    async def save(self, session: Session) -> None:
        path = self._user_dir(session.user_id) / f"{session.session_id}.json"
        data = msgspec.json.encode(session)
        await asyncio.to_thread(path.write_bytes, data)

    async def get_recent(self, user_id: int, limit: int = 3) -> list[Session]:
        user_dir = self._user_dir(user_id)
        paths = sorted(user_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        sessions = []
        for path in paths[:limit]:
            data = await asyncio.to_thread(path.read_bytes)
            sessions.append(msgspec.json.decode(data, type=Session))
        return sessions
