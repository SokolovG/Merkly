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
from src.infrastructure.telegram.messages import (
    all_cards_deleted,
    card_deleted,
    card_not_found,
    delete_all_label,
    delete_card_label,
    fetching_vocab,
    help_text,
    lesson_failed,
    no_profile,
    preparing_lesson,
    preparing_writing,
    reviewing_answers,
    reviewing_writing,
    session_expired,
    vocab_empty,
    vocab_failed,
    vocab_header,
    welcome_back,
    writing_cards_header,
)
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
    """Inline keyboard with delete buttons (2 per row) + delete all."""
    btns = [
        InlineKeyboardButton(text=delete_card_label(card.word), callback_data=f"delcard:{i}")
        for i, card in enumerate(cards)
    ]
    rows = [btns[i : i + 2] for i in range(0, len(btns), 2)]
    if len(cards) > 1:
        rows.append([InlineKeyboardButton(text=delete_all_label(), callback_data="delcard:all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        await message.answer(welcome_back(profile.level, profile.goal))
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
        await message.answer(no_profile())
        return

    await message.answer(preparing_lesson())

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
        await message.answer(lesson_failed(str(e)))
        return

    session_id = str(uuid.uuid4())[:8]

    article_msg = (
        f"📰 <b>{escape(title)}</b>\n\n"
        f"{escape(text[:1500])}\n\n"
        f"---\n"
        f"Now answer these questions in {escape(lang_name(profile.target_lang))}"
        " (or your native language if stuck):\n\n"
    )
    for i, q in enumerate(questions, 1):
        article_msg += f"<b>{i}.</b> {escape(q)}\n"

    article_msg += "\nSend your answers as one message (answer all 3)."

    await message.answer(article_msg, parse_mode="HTML")

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
        await message.answer(no_profile())
        return

    # Parse args: /vocab | /vocab 5 | /vocab university | /vocab university 5
    # Strip command prefix including optional @botname (e.g. "/vocab@bot cooking 1" -> "cooking 1")
    text = message.text or ""
    cmd_end = text.find(" ")
    args_str = text[cmd_end:].strip() if cmd_end != -1 else ""

    force_topic: str | None = None
    count: int = profile.vocab_card_count

    if args_str:
        parts = args_str.split(maxsplit=1)
        if parts[0].isdigit():
            # /vocab 5 [topic]
            count = int(parts[0])
            force_topic = parts[1].strip() if len(parts) == 2 else None
        else:
            # /vocab [topic] [count] or /vocab [topic]
            rparts = args_str.rsplit(maxsplit=1)
            if len(rparts) == 2 and rparts[1].isdigit():
                force_topic = rparts[0].strip() or None
                count = int(rparts[1])
            elif args_str.isdigit():
                count = int(args_str)
            else:
                force_topic = args_str

    recent = _vocab_topics.get(user_id, [])
    await message.answer(fetching_vocab())
    try:
        topic_name, cards = await agent.topic_vocab_lesson(
            level=profile.level,
            goal=profile.goal,
            native_lang=profile.native_lang,
            target_lang=profile.target_lang,
            recent_topics=recent,
            count=count,
            force_topic=force_topic,
        )
    except Exception as e:
        await message.answer(vocab_failed(str(e)))
        return

    if not cards:
        await message.answer(vocab_empty())
        return

    recent.append(topic_name)
    _vocab_topics[user_id] = recent[-5:]

    card_list = "\n".join(f"• {escape(c.word)} → {escape(c.translation)}" for c in cards)
    response = f"{vocab_header(topic_name, len(cards))}\n\n{card_list}"
    _last_cards[user_id] = cards
    await message.answer(response, parse_mode="HTML", reply_markup=_cards_keyboard(cards))


@router.message(Command("help"))
async def cmd_help(
    message: Message,
    profile_repo: FromDishka[JsonProfileRepository],
) -> None:
    profile = await profile_repo.get(message.from_user.id) if message.from_user else None
    count = profile.vocab_card_count if profile else 8
    await message.answer(help_text(count), parse_mode="HTML")


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

    del _pending_sessions[user_id]

    await message.answer(reviewing_answers())

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
        await callback.answer(session_expired())
        return
    mode = callback.data.split(":", 1)[1]  # type: ignore  # "sentences" | "grammar" | "article"
    await callback.answer()
    await callback.message.answer(preparing_writing())  # type: ignore
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
    await message.answer(reviewing_writing())
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
        response += f"\n\n{writing_cards_header(len(cards))}\n{card_list}"
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

    gateway: ICardGateway = agent._anki

    if action == "all":
        for card in cards:
            if card.backend_id:
                await gateway.delete_card(card.backend_id)
        _last_cards.pop(user_id, None)
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore
        await callback.answer(all_cards_deleted())
        return

    idx = int(action)
    if idx >= len(cards):
        await callback.answer(card_not_found())
        return

    card = cards[idx]
    if card.backend_id:
        await gateway.delete_card(card.backend_id)

    cards.pop(idx)
    _last_cards[user_id] = cards
    await callback.answer(card_deleted(card.word))

    if cards:
        await callback.message.edit_reply_markup(reply_markup=_cards_keyboard(cards))  # type: ignore
    else:
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore
