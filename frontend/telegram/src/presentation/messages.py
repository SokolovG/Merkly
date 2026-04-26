"""Bot reply strings — frontend copy of messages module."""


def no_profile() -> str:
    return "👋 Looks like you haven't set up your profile yet.\n\nSend /start to begin onboarding."


def help_text(count: int = 8) -> str:
    return (
        "🤖 <b>Language Tutor Bot</b>\n\n"
        "<b>Session commands:</b>\n"
        "/session — Auto-start (reading or listening, picked from your profile)\n"
        "/reading — Start a reading session directly\n"
        "/listen — Start a listening session directly\n"
        "/writing — Standalone writing task (pick a topic → AI generates the task)\n"
        "/next — Skip current step, start a new session\n"
        "/lesson — Manual picker: reading, listening, or vocab\n\n"
        "<b>Vocabulary:</b>\n"
        f"/vocab — Vocabulary cards (default: {count})\n"
        "  · <code>/vocab 5</code> — specific count\n"
        "  · <code>/vocab travel 10</code> — topic + count\n"
        # "/repeat — Review your saved word history\n\n" # TODO
        "<b>Other:</b>\n"
        "/exit — Cancel the active session early\n"
        "/help — Show this message\n\n"
        "<b>Capture words:</b>\n"
        "<code>+Brot</code> — generate a full card for any word\n"
        "<code>+Bank/furniture</code> — with context hint for better translation\n\n"
        "<b>How reading/listening sessions work:</b>\n"
        "1. Bot sends an article or audio + comprehension questions\n"
        "2. You reply with all answers in <b>one message</b>\n"
        "3. Bot reviews and gives feedback\n"
        "4. Optional writing exercise (sentences / grammar / essay)\n"
        "After feedback you'll see buttons: 📖 Another article · 🎧 Another audio · ✍️ New writing task\n"
        "Sessions expire after <b>15 min</b> of inactivity.\n\n"
        "<b>How standalone writing works:</b>\n"
        "1. /writing → bot shows topic options for your language and level\n"
        "2. Pick a topic → bot generates a writing task\n"
        "3. Write your response and send it as one message\n"
        "4. Bot gives feedback + saves vocab cards\n\n"
        "<b>Vocab cards:</b>\n"
        "Cards come from your pre-generated pool. When the pool runs low, "
        "new cards are generated live via AI. Each card includes word, "
        "translation, example sentence, word type, and article for nouns."
    )


def session_cancelled() -> str:
    return "✅ Lesson cancelled. Start a new one anytime."


def unknown_message() -> str:
    return "❓ I didn't understand that.\n\nPlease see /help command"


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
        f"⚠️ {activity.capitalize()} is not in your learning strategy.\nUse /settings to enable it."
    )


def preparing_lesson() -> str:
    return "⏳ Preparing your lesson…"


def fetching_vocab() -> str:
    return "⏳ Fetching vocabulary…"


def card_saved(word: str, deck_name: str) -> str:
    return f"📥 Saved: <b>{word}</b> → <i>{deck_name}</i>"


def card_saved_no_deck(word: str) -> str:
    return f"📥 Saved: <b>{word}</b>"


def word_already_exists(word: str) -> str:
    return f"✅ <b>{word}</b> is already in your vocabulary history."


def lesson_picker() -> str:
    return "Choose a lesson type:"
