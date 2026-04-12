from html import escape

from src.domain.entities import DEFAULT_VOCAB_CARD_COUNT

# --- Onboarding / profile ---


def welcome_back(level: str, goal: str, vocab_card_count: int = DEFAULT_VOCAB_CARD_COUNT) -> str:
    return (
        f"Welcome back! 👋  Level: <b>{level}</b>  |  Goal: <b>{goal}</b>\n\n"
        "<b>What you can do:</b>\n"
        "/session — reading lesson (article + questions + writing)\n"
        "/listen — listening lesson from a podcast\n"
        f"/vocab — {vocab_card_count} vocabulary cards on a rotating topic\n"
        "/settings — change language, level, strategy\n"
        "/help — full command reference\n\n"
        "<i>Tip: type <b>+word</b> anywhere to capture a word instantly.</i>"
    )


def no_profile() -> str:
    return "Please set up your profile first. Type /start"


def complete_setup() -> str:
    return "Please complete setup first — type /start"


# --- Session ---


def preparing_lesson() -> str:
    return "Preparing your lesson... ⏳"


def lesson_failed(error: str) -> str:
    return f"Failed to prepare lesson: {error}\nPlease try again."


def reviewing_answers() -> str:
    return "Reviewing your answers... 🤔"


def session_expired() -> str:
    return "Session expired. Start a new /session."


# --- Writing exercise ---


def preparing_writing() -> str:
    return "Preparing your writing task... ✍️"


def reviewing_writing() -> str:
    return "Reviewing your writing... 🤔"


def writing_cards_header(count: int) -> str:
    return f"🃏 <b>Flashcards saved ({count}):</b>"


# --- Vocab ---


def fetching_vocab() -> str:
    return "Fetching vocabulary for you... ⏳"


def vocab_failed(error: str) -> str:
    return f"Failed to fetch vocabulary: {error}\nPlease try again."


def vocab_empty() -> str:
    return "Couldn't generate vocabulary this time. Try /vocab again."


def vocab_header(topic: str, count: int) -> str:
    return f"🃏 <b>{escape(topic)} ({count} words):</b>"


def vocab_fetch_failed() -> str:
    return "Couldn't fetch vocabulary. Try /vocab again."


def vocab_not_found() -> str:
    return "No vocabulary found. Try /vocab again."


# --- Repeat ---


def repeat_header(count: int) -> str:
    return f"🔁 <b>Repeat ({count} words)</b>\n\nTry to recall each translation:\n\n"


def repeat_empty() -> str:
    return "No vocab history yet. Run /vocab first to build your word bank."


# --- Word capture ---


def looking_up(word: str) -> str:
    return f"Looking up <b>{escape(word)}</b>... ⏳"


def word_empty() -> str:
    return "Please add a word after +, e.g. <b>+Brot</b>"


def card_saved(
    display_word: str,
    translation: str,
    example: str,
    grammar_note: str | None = None,
    deck_name: str | None = None,
) -> str:
    note_line = f"\n<i>{escape(grammar_note)}</i>" if grammar_note else ""
    saved_to = f"📥 Saved to <b>{escape(deck_name)}</b>" if deck_name else "📥 Saved to your deck"
    return (
        f"✅ <b>{escape(display_word)}</b> — {escape(translation)}\n"
        f"<i>{escape(example)}</i>"
        f"{note_line}\n"
        f"{saved_to}"
    )


def card_saved_no_backend(
    display_word: str,
    translation: str,
    example: str,
    grammar_note: str | None = None,
    deck_name: str | None = None,
) -> str:
    note_line = f"\n<i>{escape(grammar_note)}</i>" if grammar_note else ""
    return (
        f"✅ <b>{escape(display_word)}</b> — {escape(translation)}\n"
        f"<i>{escape(example)}</i>"
        f"{note_line}\n"
        "⚠️ Card saved locally (deck not connected)"
    )


def word_capture_failed(word: str) -> str:
    return f"Couldn't generate a card for <b>{escape(word)}</b>. Try again or check the spelling."


def word_capture_error() -> str:
    return "Something went wrong adding the card. Please try again."


# --- Word capture: regenerate flow ---


def ask_for_context() -> str:
    return (
        "What context? Send anything — a word, phrase, or sentence.\n"
        "(e.g. <i>slang</i>, <i>food</i>, <i>Dialect</i>)"
    )


def regenerating(word: str) -> str:
    return f"Regenerating card for <b>{escape(word)}</b>... ⏳"


# --- Cards keyboard labels ---


def delete_card_label(word: str) -> str:
    return f"🗑 {word}"


def delete_all_label() -> str:
    return "🗑 Delete all"


def card_deleted(word: str) -> str:
    return f"Deleted: {word}"


def all_cards_deleted() -> str:
    return "All cards deleted."


def card_not_found() -> str:
    return "Card not found."


# --- Deck management ---


def deck_created(name: str) -> str:
    return f"✅ Deck <b>{escape(name)}</b> created and set as active."


def deck_selected(name: str) -> str:
    return f"✅ Active deck set to <b>{escape(name)}</b>."


def deck_no_decks() -> str:
    return "No decks found. Create one with /newdeck &lt;name&gt;"


def deck_pick_active() -> str:
    return "Choose your active deck:"


def deck_backend_error(detail: str) -> str:
    return f"Card backend error: {escape(detail)}"


# --- Listening ---


def listening_disabled() -> str:
    return (
        "🎧 Listening lessons are disabled in your settings.\nEnable them in /settings → Strategy."
    )


def listening_fetching() -> str:
    return "🎧 Finding a podcast episode for you..."


def listening_transcribing() -> str:
    return "✍️ Transcribing audio... (this takes ~10–20 seconds)"


def listening_questions(questions: str) -> str:
    return (
        f"📝 Listen carefully, then answer these questions:\n\n{questions}\n\n"
        "Send your answers when ready."
    )


# --- Strategy ---


def strategy_not_enabled(activity: str) -> str:
    return f"📋 {activity.capitalize()} is not in your active strategy.\nEnable it via /settings."


# --- Settings: session/listening options ---


def settings_qcount_updated(n: int) -> str:
    return f"✅ Questions per session set to {n}."


def settings_duration_updated(n: int) -> str:
    return f"✅ Podcast clip length set to {n} minutes."


def settings_duration_custom_prompt() -> str:
    return "Send the desired clip length in minutes (1–60):"


def settings_duration_invalid() -> str:
    return "❌ Please send a number between 1 and 60."


# --- Help ---


def help_text(vocab_card_count: int = DEFAULT_VOCAB_CARD_COUNT) -> str:
    return (
        "📚 <b>Language Tutor — Commands</b>\n\n"
        "/session — Start a reading lesson\n"
        "/listen — Start a listening lesson from a podcast\n"
        f"/vocab — Vocabulary cards ({vocab_card_count} words, topic rotates)\n"
        "/repeat — Review previously seen words (oldest first, no cards created)\n"
        "/clearvocab — Clear vocab pool (use after changing level or to force fresh words)\n"
        "/settings — Update your profile (language, level, goal, card count)\n"
        "/newdeck &lt;name&gt; — Create a new deck in Anki/Mochi and set it as active\n"
        "/setdeck — Pick your active deck from existing ones\n"
        "/bug — Report a bug\n"
        "/exit — Cancel active session\n"
        "/help — Show this message\n\n"
        "📖 How a session works:\n"
        "1. Bot fetches an article in your target language\n"
        "2. Answer comprehension questions\n"
        "3. Get honest feedback\n"
        "4. Optional writing exercise:\n"
        "   ✍️ Sentences — 2–3 sentences with article words\n"
        "   📝 Grammar — practice a grammar structure\n"
        "   📰 Essay — 200+ word formal text (exam prep)\n"
        "5. Writing feedback + flashcards from your mistakes\n\n"
        "🎧 How a listening lesson works:\n"
        "1. Bot finds a podcast episode in your target language\n"
        "2. Listen to the clip\n"
        "3. Answer comprehension questions\n"
        "4. Get feedback\n\n"
        "🃏 Capture any word instantly: type <b>+word</b> (e.g. <b>+Brot</b>)\n"
        "   Cards go to your active deck (/setdeck to change)\n\n"
        "🃏 Cards can be deleted with the buttons below each card list."
    )


# --- Bug report ---


def bug_report_sent() -> str:
    return "✅ Report sent. Thank you!"


def bug_report_prompt() -> str:
    return "🐛 Describe the bug (text, photo, video, or PDF):"


def bug_report_unsupported_file() -> str:
    return "❌ Unsupported file type. Please send text, photo, video, or PDF."


# --- Unknown message ---


def unknown_message() -> str:
    return (
        "I didn't understand that.\n\n"
        "Available commands:\n"
        "/session — reading lesson\n"
        "/listen — listening lesson\n"
        "/vocab — vocabulary cards\n"
        "/repeat — review past words\n"
        "/settings — preferences\n"
        "/bug — report a bug\n"
        "/exit — cancel active session\n"
        "/help — full help"
    )


def session_cancelled() -> str:
    return "Session cancelled. Use /session, /vocab, or /listen to start a new one."
