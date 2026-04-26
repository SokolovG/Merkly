import msgspec


class SessionState(msgspec.Struct):
    session_id: str
    user_id: str
    session_type: str  # "reading" | "listening" | "writing"
    state: str  # "questions" | "writing" | "complete"
    target_lang: str
    title: str
    url: str
    text: str
    questions: list[str]
    user_answers: list[str]
    feedback: str | None = None
    writing_text: str | None = None
    writing_feedback: str | None = None
    writing_task_text: str | None = None
    theme: str | None = None
    level: str = ""
    native_lang: str = ""
    question_count: int = 0
    audio_url: str | None = None
    created_at: str = ""
