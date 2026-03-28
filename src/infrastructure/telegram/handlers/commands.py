import uuid
from datetime import datetime
from html import escape

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_dialog import DialogManager, StartMode
from dishka.integrations.aiogram import FromDishka

from src.application.agent.core import LessonAgent
from src.application.agent.prompts import lang_name
from src.domain.entities import Session, VocabCard
from src.domain.ports.card_gateway import ICardGateway
from src.infrastructure.repositories.json_profile_repo import JsonProfileRepository
from src.infrastructure.repositories.json_session_repo import JsonSessionRepository
from src.infrastructure.telegram.states import OnboardingSG

router = Router()

# Simple in-memory stores (fine for hackathon)
_pending_sessions: dict[int, dict] = {}
_pending_writing: dict[int, dict] = {}
_vocab_topics: dict[int, list[str]] = {}
_last_cards: dict[int, list[VocabCard]] = {}


class _HasPendingSession(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in _pending_sessions


class _HasPendingWriting(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        uid = message.from_user.id if message.from_user else None
        return (
            uid is not None and _pending_writing.get(uid, {}).get("state") == "waiting_for_writing"
        )


def _cards_keyboard(cards: list[VocabCard]) -> InlineKeyboardMarkup:
    """Inline keyboard with a delete button per card + delete all."""
    buttons = []
    for i, card in enumerate(cards):
        label = f"🗑 {card.word}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"delcard:{i}")])
    buttons.append([InlineKeyboardButton(text="🗑 Delete all", callback_data="delcard:all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    dialog_manager: DialogManager,
    profile_repo: FromDishka[JsonProfileRepository],
) -> None:
    user_id = message.from_user.id  # type: ignore
    _pending_sessions.pop(user_id, None)
    profile = await profile_repo.get(user_id)

    if profile:
        await message.answer(
            f"Welcome back! 👋\n"
            f"Your level: {profile.level} | Goal: {profile.goal}\n\n"
            "Type /session to start today's lesson."
        )
    else:
        await dialog_manager.start(OnboardingSG.target_lang, mode=StartMode.RESET_STACK)


@router.message(Command("session"))
async def cmd_session(
    message: Message,
    profile_repo: FromDishka[JsonProfileRepository],
    session_repo: FromDishka[JsonSessionRepository],
    agent: FromDishka[LessonAgent],
) -> None:
    user_id = message.from_user.id  # type: ignore
    profile = await profile_repo.get(user_id)

    if not profile:
        await message.answer("Please set up your profile first. Type /start")
        return

    await message.answer("Preparing your lesson... ⏳")

    # Get recent session topics to avoid repetition
    recent = await session_repo.get_recent(user_id, limit=3)
    recent_topics = [s.article_title for s in recent]

    try:
        title, url, text, questions = await agent.prepare_lesson(
            level=profile.level,
            goal=profile.goal,
            native_lang=profile.native_lang,
            target_lang=profile.target_lang,
            session_minutes=profile.session_minutes,
            recent_topics=recent_topics,
        )
    except Exception as e:
        await message.answer(f"Failed to prepare lesson: {e}\nPlease try again.")
        return

    # Store session context in FSM via a simple approach
    # We'll use message state to track the session
    session_id = str(uuid.uuid4())[:8]

    from html import escape

    article_msg = (
        f"📰 <b>{escape(title)}</b>\n\n"
        f"{escape(text[:1500])}\n\n"
        f"---\n"
        f"Now answer these questions in {escape(lang_name(profile.target_lang))} (or your native language if stuck):\n\n"
    )
    for i, q in enumerate(questions, 1):
        article_msg += f"<b>{i}.</b> {escape(q)}\n"

    article_msg += "\nSend your answers as one message (answer all 3)."

    await message.answer(article_msg, parse_mode="HTML")

    # Store context for answer collection
    # Using a simple module-level dict for hackathon speed
    _pending_sessions[user_id] = {
        "session_id": session_id,
        "title": title,
        "url": url,
        "text": text,
        "questions": questions,
        "level": profile.level,
        "native_lang": profile.native_lang,
        "target_lang": profile.target_lang,
    }


@router.message(Command("vocab"))
async def cmd_vocab(
    message: Message,
    profile_repo: FromDishka[JsonProfileRepository],
    agent: FromDishka[LessonAgent],
) -> None:
    user_id = message.from_user.id  # type: ignore
    profile = await profile_repo.get(user_id)
    if not profile:
        await message.answer("Please set up your profile first. Type /start")
        return

    recent = _vocab_topics.get(user_id, [])
    await message.answer("Fetching vocabulary for you... ⏳")
    try:
        topic_name, cards = await agent.topic_vocab_lesson(
            level=profile.level,
            goal=profile.goal,
            native_lang=profile.native_lang,
            target_lang=profile.target_lang,
            recent_topics=recent,
        )
    except Exception as e:
        await message.answer(f"Failed to fetch vocabulary: {e}\nPlease try again.")
        return

    if not cards:
        await message.answer("Couldn't generate vocabulary this time. Try /vocab again.")
        return

    recent.append(topic_name)
    _vocab_topics[user_id] = recent[-5:]

    card_list = "\n".join(f"• {escape(c.word)} → {escape(c.translation)}" for c in cards)
    response = f"🃏 <b>{escape(topic_name)} ({len(cards)} words):</b>\n\n{card_list}"
    _last_cards[user_id] = cards
    await message.answer(response, parse_mode="HTML", reply_markup=_cards_keyboard(cards))


@router.message(Command("skip", "pass"))
async def cmd_skip(
    message: Message,
    profile_repo: FromDishka[JsonProfileRepository],
    agent: FromDishka[LessonAgent],
) -> None:
    await cmd_vocab(message, profile_repo, agent)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📚 <b>Language Tutor — Commands</b>\n\n"
        "/session — Start today's lesson (article + 3 questions)\n"
        "/vocab — Goal-aware vocabulary cards (8 words, topic rotates)\n"
        "/skip — Same as /vocab\n"
        "/settings — Update your profile (language, level, goal)\n"
        "/help — Show this message\n\n"
        "📖 How a session works:\n"
        "1. Bot fetches an article in your target language\n"
        "2. Answer 3 comprehension questions\n"
        "3. Get honest feedback (no cards from reading)\n"
        "4. Choose a writing exercise:\n"
        "   ✍️ Sentences — 2–3 sentences with article words\n"
        "   📝 Grammar — practice a grammar structure\n"
        "   📰 Essay — 200+ word formal text (exam prep)\n"
        "5. Writing feedback + flashcards from your mistakes\n\n"
        "🃏 Cards can be deleted with the buttons below each card list."
    )


@router.message(Command("settings"))
async def cmd_settings(
    message: Message,
    profile_repo: FromDishka[JsonProfileRepository],
    dialog_manager: DialogManager,
) -> None:
    # Clear any pending session so typed dialog inputs aren't treated as article answers
    _pending_sessions.pop(message.from_user.id, None)  # type: ignore
    await dialog_manager.start(OnboardingSG.target_lang, mode=StartMode.RESET_STACK)


@router.message(_HasPendingSession())
async def handle_answer(
    message: Message,
    profile_repo: FromDishka[JsonProfileRepository],
    session_repo: FromDishka[JsonSessionRepository],
    agent: FromDishka[LessonAgent],
) -> None:
    user_id = message.from_user.id  # type: ignore
    ctx = _pending_sessions.get(user_id)

    if not ctx or not message.text:
        return

    # User wants to skip the reading — give vocab cards instead
    if message.text.strip().lower() in ("/skip", "/pass"):
        del _pending_sessions[user_id]
        profile = await profile_repo.get(user_id)
        if not profile:
            return
        recent = _vocab_topics.get(user_id, [])
        await message.answer("Skipping reading... fetching vocabulary instead ⏳")
        try:
            topic_name, cards = await agent.topic_vocab_lesson(
                level=profile.level,
                goal=profile.goal,
                native_lang=profile.native_lang,
                target_lang=profile.target_lang,
                recent_topics=recent,
            )
        except Exception:
            await message.answer("Couldn't fetch vocabulary. Try /vocab again.")
            return
        if cards:
            recent.append(topic_name)
            _vocab_topics[user_id] = recent[-5:]
            card_list = "\n".join(f"• {escape(c.word)} → {escape(c.translation)}" for c in cards)
            response = f"🃏 <b>{escape(topic_name)} ({len(cards)} words):</b>\n\n{card_list}"
            _last_cards[user_id] = cards
            await message.answer(response, parse_mode="HTML", reply_markup=_cards_keyboard(cards))
        else:
            await message.answer("No vocabulary found. Try /vocab again.")
        return

    del _pending_sessions[user_id]

    await message.answer("Reviewing your answers... 🤔")

    # Use the full text as answers (simple: one message for all 3)
    answers = [message.text]

    feedback, _ = await agent.review_answers(
        article_text=ctx["text"],
        questions=ctx["questions"],
        answers=answers,
        level=ctx["level"],
        native_lang=ctx["native_lang"],
        target_lang=ctx["target_lang"],
    )

    # Store context for optional writing exercise
    _pending_writing[user_id] = {
        "article_text": ctx["text"],
        "target_lang": ctx["target_lang"],
        "level": ctx["level"],
        "native_lang": ctx["native_lang"],
        "state": "offered",
    }

    writing_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✍️ Sentences", callback_data="writing:sentences"),
                InlineKeyboardButton(text="📝 Grammar", callback_data="writing:grammar"),
                InlineKeyboardButton(text="📰 Essay text", callback_data="writing:article"),
            ]
        ]
    )
    response = f"📝 <b>Feedback:</b>\n\n{escape(feedback)}"
    await message.answer(response, parse_mode="HTML", reply_markup=writing_kb)

    # Save session
    session = Session(
        session_id=ctx["session_id"],
        user_id=user_id,
        date=datetime.now().isoformat(),
        article_url=ctx["url"],
        article_title=ctx["title"],
        article_text=ctx["text"],
        questions=ctx["questions"],
        user_answers=answers,
        feedback=feedback,
        cards_created=[],
    )
    await session_repo.save(session)


@router.callback_query(F.data.startswith("writing:"))
async def handle_writing_exercise_start(
    callback: CallbackQuery,
    agent: FromDishka[LessonAgent],
) -> None:
    user_id = callback.from_user.id
    ctx = _pending_writing.get(user_id)
    if not ctx:
        await callback.answer("Session expired. Start a new /session.")
        return
    mode = callback.data.split(":", 1)[1]  # type: ignore  # "sentences" | "grammar" | "article"
    await callback.answer()
    await callback.message.answer("Preparing your writing task... ✍️")  # type: ignore
    task = await agent.generate_writing_task(
        ctx["article_text"], ctx["target_lang"], ctx["level"], mode
    )
    _pending_writing[user_id]["state"] = "waiting_for_writing"
    _pending_writing[user_id]["task"] = task
    _pending_writing[user_id]["mode"] = mode
    mode_label = {
        "sentences": "✍️ Sentences",
        "grammar": "📝 Grammar focus",
        "article": "📰 Essay",
    }.get(mode, "✍️ Writing exercise")
    await callback.message.answer(  # type: ignore
        f"<b>{mode_label}:</b>\n\n{escape(task)}", parse_mode="HTML"
    )


@router.message(_HasPendingWriting())
async def handle_writing(
    message: Message,
    agent: FromDishka[LessonAgent],
) -> None:
    user_id = message.from_user.id  # type: ignore
    ctx = _pending_writing.pop(user_id, None)
    if not ctx or not message.text:
        return
    await message.answer("Reviewing your writing... 🤔")
    feedback, cards = await agent.review_writing(
        writing_task=ctx["task"],
        user_writing=message.text,
        level=ctx["level"],
        native_lang=ctx["native_lang"],
        target_lang=ctx["target_lang"],
        mode=ctx.get("mode", "sentences"),
    )
    response = f"✍️ <b>Writing feedback:</b>\n\n{escape(feedback)}"
    if cards:
        card_list = "\n".join(f"• {escape(c.word)} → {escape(c.translation)}" for c in cards)
        response += f"\n\n🃏 <b>Flashcards saved ({len(cards)}):</b>\n{card_list}"
        _last_cards[user_id] = cards
        await message.answer(response, parse_mode="HTML", reply_markup=_cards_keyboard(cards))
    else:
        await message.answer(response, parse_mode="HTML")


@router.callback_query(F.data.startswith("delcard:"))
async def handle_delete_card(
    callback: CallbackQuery,
    agent: FromDishka[LessonAgent],
) -> None:
    user_id = callback.from_user.id
    cards = _last_cards.get(user_id, [])
    action = callback.data.split(":", 1)[1]  # type: ignore

    gateway: ICardGateway = agent._anki  # type: ignore

    if action == "all":
        for card in cards:
            if card.backend_id:
                await gateway.delete_card(card.backend_id)
        _last_cards.pop(user_id, None)
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore
        await callback.answer("All cards deleted.")
        return

    idx = int(action)
    if idx >= len(cards):
        await callback.answer("Card not found.")
        return

    card = cards[idx]
    if card.backend_id:
        await gateway.delete_card(card.backend_id)

    cards.pop(idx)
    _last_cards[user_id] = cards
    await callback.answer(f"Deleted: {card.word}")

    if cards:
        await callback.message.edit_reply_markup(reply_markup=_cards_keyboard(cards))  # type: ignore
    else:
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore
