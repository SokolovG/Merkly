"""Bot reply strings — frontend copy of messages module."""


def no_profile() -> str:
    return (
        "👋 Looks like you haven't set up your profile yet.\n\n" "Send /start to begin onboarding."
    )


def help_text(count: int = 8) -> str:
    return (
        "🤖 <b>Language Tutor Bot</b>\n\n"
        "<b>Commands:</b>\n"
        "/session — Reading lesson\n"
        "/listen — Listening lesson\n"
        f"/vocab — Vocabulary cards (default: {count})\n"
        "/repeat — Review past words\n"
        "/help — Show this message\n"
        "/exit — Cancel active lesson\n\n"
        "<b>Capture words:</b>\n"
        "+word — Save any word instantly (e.g. +Brot)\n"
        "+word/context — With context hint (e.g. +Bank/furniture)"
    )


def session_cancelled() -> str:
    return "✅ Lesson cancelled. Start a new one anytime."


def unknown_message() -> str:
    return (
        "❓ I didn't understand that.\n\n"
        "Available commands: /session, /listen, /vocab, /repeat, /help\n"
        "Or capture a word: +word"
    )


def vocab_header(topic: str, count: int) -> str:
    return f"📚 <b>{topic}</b> — {count} cards"


def repeat_header(count: int) -> str:
    return f"🔁 <b>Review — {count} words:</b>\n\n"


def repeat_empty() -> str:
    return "📭 No words to review yet. Use /vocab to build your history."


def vocab_empty() -> str:
    return "📭 No vocab cards available. Try again in a moment."


def vocab_failed(error: str) -> str:
    return f"❌ Couldn't generate vocab: {error}"


def lesson_failed(error: str) -> str:
    return f"❌ Couldn't prepare lesson: {error}"


def listening_disabled() -> str:
    return "🔇 Listening lessons are not enabled in your strategy.\nUse /settings to enable them."


def strategy_not_enabled(activity: str) -> str:
    return (
        f"⚠️ {activity.capitalize()} is not in your learning strategy.\n"
        "Use /settings to enable it."
    )


def preparing_lesson() -> str:
    return "⏳ Preparing your lesson…"


def fetching_vocab() -> str:
    return "⏳ Fetching vocabulary…"


def card_saved(word: str, deck_name: str) -> str:
    return f"📥 Saved: <b>{word}</b> → <i>{deck_name}</i>"


def card_saved_no_deck(word: str) -> str:
    return f"📥 Saved: <b>{word}</b>"
