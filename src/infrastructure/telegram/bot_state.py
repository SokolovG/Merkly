from dataclasses import dataclass, field

from src.domain.entities import VocabCard


@dataclass
class BotStateStore:
    """In-memory state for active Telegram sessions.

    Intentionally volatile — lost on restart, acceptable for demo use.
    Replace with a Redis-backed store for multi-process or production deployments.
    """

    pending_sessions: dict[int, dict] = field(default_factory=dict)
    pending_writing: dict[int, dict] = field(default_factory=dict)
    vocab_topics: dict[int, list[str]] = field(default_factory=dict)
    last_cards: dict[int, list[VocabCard]] = field(default_factory=dict)
