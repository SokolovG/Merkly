from html import escape

from src.domain.entities import DEFAULT_VOCAB_CARD_COUNT

# --- Onboarding / profile ---


def welcome_back(level: str, goal: str) -> str:
    return (
        f"Welcome back! 👋\n"
        f"Your level: {level} | Goal: {goal}\n\n"
        "Type /session to start today's lesson."
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


# --- Word capture ---


def looking_up(word: str) -> str:
    return f"Looking up <b>{escape(word)}</b>... ⏳"


def word_empty() -> str:
    return "Please add a word after +, e.g. <b>+Brot</b>"


def card_saved(display_word: str, translation: str, example: str) -> str:
    return (
        f"✅ <b>{escape(display_word)}</b> — {escape(translation)}\n"
        f"<i>{escape(example)}</i>\n"
        "📥 Saved to your deck"
    )


def card_saved_no_backend(display_word: str, translation: str, example: str) -> str:
    return (
        f"✅ <b>{escape(display_word)}</b> — {escape(translation)}\n"
        f"<i>{escape(example)}</i>\n"
        "⚠️ Card saved locally (deck not connected)"
    )


def word_capture_failed(word: str) -> str:
    return f"Couldn't generate a card for <b>{escape(word)}</b>. Try again or check the spelling."


def word_capture_error() -> str:
    return "Something went wrong adding the card. Please try again."


# --- Word capture: regenerate flow ---


def ask_for_context() -> str:
    return (
        "Send context for the word "
        "(e.g. <i>slang</i>, <i>food</i>, <i>Sprichwort</i>, <i>biology</i>)"
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


# --- Help ---


def help_text(vocab_card_count: int = DEFAULT_VOCAB_CARD_COUNT) -> str:
    return (
        "📚 <b>Language Tutor — Commands</b>\n\n"
        "/session — Start today's lesson\n"
        f"/vocab — Vocabulary cards ({vocab_card_count} words, topic rotates)\n"
"/settings — Update your profile (language, level, goal, card count)\n"
        "/newdeck &lt;name&gt; — Create a new deck in Anki/Mochi and set it as active\n"
        "/setdeck — Pick your active deck from existing ones\n"
        "/help — Show this message\n\n"
        "📖 How a session works:\n"
        "1. Bot fetches an article in your target language\n"
        "2. Answer 3 comprehension questions\n"
        "3. Get honest feedback\n"
        "4. Optional writing exercise:\n"
        "   ✍️ Sentences — 2–3 sentences with article words\n"
        "   📝 Grammar — practice a grammar structure\n"
        "   📰 Essay — 200+ word formal text (exam prep)\n"
        "5. Writing feedback + flashcards from your mistakes\n\n"
        "🃏 Capture any word instantly: type <b>+word</b> (e.g. <b>+Brot</b>)\n"
        "   Cards go to your active deck (/setdeck to change)\n\n"
        "🃏 Cards can be deleted with the buttons below each card list."
    )
