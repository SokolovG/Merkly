import asyncio
import contextlib
import uuid
from datetime import datetime
from html import escape

import structlog
from aiogram import F, Router
from aiogram.filters import BaseFilter, Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_dialog import DialogManager, StartMode
from dishka.integrations.aiogram import FromDishka

from src.application.agent.core import LessonAgent
from src.application.agent.prompts import lang_name
from src.application.article_refill_service import ArticleRefillService
from src.application.vocab_refill_service import VocabRefillService
from src.domain.entities import Session, VocabCard
from src.domain.enums import ActivityType
from src.domain.ports.card_gateway import ICardGateway
from src.infrastructure.database.repositories import ProfileRepository, SessionRepository
from src.infrastructure.database.repositories.article_pool_repo import ArticlePoolRepository
from src.infrastructure.database.repositories.session_history_repo import SessionHistoryRepository
from src.infrastructure.database.repositories.vocab_pool_repo import VocabPoolRepository
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
    repeat_empty,
    repeat_header,
    reviewing_answers,
    reviewing_writing,
    session_cancelled,
    session_expired,
    strategy_not_enabled,
    unknown_message,
    vocab_empty,
    vocab_failed,
    vocab_header,
    welcome_back,
    writing_cards_header,
)
from src.infrastructure.telegram.states import BugSG, OnboardingSG

router = Router()
catch_all_router = Router()  # Registered last so it doesn't intercept dialog messages

logger = structlog.get_logger(__name__)

_CB_DEL_CARD = "delcard"
_CB_WRITING = "writing"

# Simple in-memory stores (fine for hackathon)
_pending_sessions: dict[int, dict] = {}
_pending_writing: dict[int, dict] = {}
_last_cards: dict[int, list[VocabCard]] = {}


class _HasPendingSession(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if (message.text or "").startswith("/"):
            return False
        return message.from_user is not None and message.from_user.id in _pending_sessions


class _HasPendingWriting(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if (message.text or "").startswith("/"):
            return False
        uid = message.from_user.id if message.from_user else None
        return (
            uid is not None and _pending_writing.get(uid, {}).get("state") == "waiting_for_writing"
        )


def _cards_keyboard(cards: list[VocabCard]) -> InlineKeyboardMarkup:
    """Inline keyboard with delete buttons (2 per row) + delete all."""
    btns = [
        InlineKeyboardButton(text=delete_card_label(card.word), callback_data=f"{_CB_DEL_CARD}:{i}")
        for i, card in enumerate(cards)
    ]
    rows = [btns[i : i + 2] for i in range(0, len(btns), 2)]
    if len(cards) > 1:
        rows.append(
            [InlineKeyboardButton(text=delete_all_label(), callback_data=f"{_CB_DEL_CARD}:all")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    dialog_manager: DialogManager,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = message.from_user.id  # type: ignore
    _pending_sessions.pop(user_id, None)
    profile = await profile_repo.get(user_id)
    if profile:
        structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)
        logger.info("cmd_start", messenger_id=user_id)

    if profile:
        await message.answer(
            welcome_back(profile.level, profile.goal, profile.vocab_card_count),
            parse_mode="HTML",
        )
    else:
        await dialog_manager.start(OnboardingSG.target_lang, mode=StartMode.RESET_STACK)


@router.message(Command("session"))
async def cmd_session(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    session_repo: FromDishka[SessionRepository],
    session_history_repo: FromDishka[SessionHistoryRepository],
    agent: FromDishka[LessonAgent],
    article_pool_repo: FromDishka[ArticlePoolRepository],
    article_refill_service: FromDishka[ArticleRefillService],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = message.from_user.id  # type: ignore
    profile = await profile_repo.get(user_id)

    if not profile:
        await message.answer(no_profile())
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)
    logger.info("cmd_session", messenger_id=user_id)

    if ActivityType.READING not in profile.learning_strategy:
        await message.answer(strategy_not_enabled("reading"))
        return

    await message.answer(preparing_lesson())

    # --- Article Pool: try pool first ---
    pooled = await article_pool_repo.get_oldest(profile.id, str(profile.target_lang))
    if pooled and not await session_history_repo.has_seen(profile.id, pooled.url):
        # Serve from pool — instant
        title, url, text, questions = pooled.title, pooled.url, pooled.text, pooled.questions
        await article_pool_repo.mark_served(pooled.id)
        logger.info("cmd_session_pool_hit", messenger_id=user_id)
    else:
        # Pool miss (empty or stale entry) — live fetch
        if pooled:
            await article_pool_repo.mark_served(pooled.id)  # discard stale
        logger.info("cmd_session_pool_miss", messenger_id=user_id)
        recent = await session_repo.get_recent(profile.id, limit=3)
        recent_topics = [s.article_title for s in recent]
        try:
            title, url, text, questions = await agent.prepare_reading_lesson(
                level=profile.level,
                goal=profile.goal,
                native_lang=profile.native_lang,
                target_lang=profile.target_lang,
                recent_topics=recent_topics,
                question_count=profile.question_count,
            )
        except Exception as e:
            await message.answer(lesson_failed(str(e)))
            return
        # Dedup retry (existing pattern, live path only)
        if await session_history_repo.has_seen(profile.id, url):
            with contextlib.suppress(Exception):
                title, url, text, questions = await agent.prepare_reading_lesson(
                    level=profile.level,
                    goal=profile.goal,
                    native_lang=profile.native_lang,
                    target_lang=profile.target_lang,
                    recent_topics=recent_topics,
                    question_count=profile.question_count,
                )

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

    article_msg += f"\nSend your answers as one message (answer all {len(questions)})."

    await message.answer(article_msg, parse_mode="HTML")
    await session_history_repo.record(profile.id, url, ActivityType.READING)

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

    # Eager refill (non-blocking — fire and forget via asyncio.create_task)
    asyncio.create_task(article_refill_service.refill_if_needed(profile))


@router.message(Command("vocab"))
async def cmd_vocab(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    agent: FromDishka[LessonAgent],
    pool_repo: FromDishka[VocabPoolRepository],
    refill_service: FromDishka[VocabRefillService],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = message.from_user.id  # type: ignore
    profile = await profile_repo.get(user_id)
    if not profile:
        await message.answer(no_profile())
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)

    if ActivityType.VOCAB not in profile.learning_strategy:
        await message.answer(strategy_not_enabled("vocab"))
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

    logger.info("cmd_vocab", messenger_id=user_id, force_topic=force_topic, count=count)

    await message.answer(fetching_vocab())

    # force_topic bypasses pool — user explicitly requested a specific topic (LLM override)
    if force_topic is not None:
        try:
            topic_name, cards = await agent.topic_vocab_lesson(
                level=profile.level,
                goal=str(profile.goal),
                native_lang=str(profile.native_lang),
                target_lang=str(profile.target_lang),
                recent_topics=[],
                count=count,
                force_topic=force_topic,
            )
        except Exception as e:
            await message.answer(vocab_failed(str(e)))
            return
        if not cards:
            await message.answer(vocab_empty())
            return
        card_list = "\n".join(f"• {escape(c.word)} → {escape(c.translation)}" for c in cards)
        response = f"{vocab_header(topic_name, len(cards))}\n\n{card_list}"
        _last_cards[user_id] = cards
        await message.answer(response, parse_mode="HTML", reply_markup=_cards_keyboard(cards))
        return

    # Normal path: serve from pool
    target_lang = str(profile.target_lang)
    pool_cards = await pool_repo.get_pool_cards(profile.id, target_lang, count)

    # On-miss fallback: trigger synchronous refill and retry once
    if not pool_cards:
        try:
            await refill_service._refill(profile)
        except Exception as e:
            await message.answer(vocab_failed(str(e)))
            return
        pool_cards = await pool_repo.get_pool_cards(profile.id, target_lang, count)

    if not pool_cards:
        await message.answer(vocab_empty())
        return

    # Create Anki/Mochi cards at serve time
    vocab_cards: list[VocabCard] = []
    deck_id = profile.active_deck_id or None
    for pc in pool_cards:
        vc = VocabCard(
            word=pc.word,
            translation=pc.translation,
            example_sentence=pc.example_sentence,
            word_type=pc.word_type,
            article=pc.article,
        )
        backend_id = await agent._card_gateway.create_card(vc, deck_id=deck_id)
        vocab_cards.append(
            VocabCard(
                word=pc.word,
                translation=pc.translation,
                example_sentence=pc.example_sentence,
                word_type=pc.word_type,
                article=pc.article,
                backend_id=backend_id,
            )
        )

    card_list = "\n".join(f"• {escape(c.word)} → {escape(c.translation)}" for c in vocab_cards)
    response = f"{vocab_header('Vocabulary', len(vocab_cards))}\n\n{card_list}"
    _last_cards[user_id] = vocab_cards
    await message.answer(response, parse_mode="HTML", reply_markup=_cards_keyboard(vocab_cards))

    # Mark served cards as shown (moves to history, removes from pool)
    await pool_repo.mark_shown(profile.id, [pc.id for pc in pool_cards])

    # Eager refill: top up pool if below threshold (runs after response sent)
    await refill_service.refill_if_needed(profile)


@router.message(Command("repeat"))
async def cmd_repeat(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    pool_repo: FromDishka[VocabPoolRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = message.from_user.id  # type: ignore
    profile = await profile_repo.get(user_id)
    if not profile:
        await message.answer(no_profile())
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)
    logger.info("cmd_repeat", messenger_id=user_id)

    words = await pool_repo.get_history_words(
        profile.id, str(profile.target_lang), limit=10, oldest_first=True
    )
    if not words:
        await message.answer(repeat_empty())
        return

    word_list = "\n".join(f"{i}. <b>{escape(w)}</b>" for i, w in enumerate(words, 1))
    await message.answer(f"{repeat_header(len(words))}{word_list}", parse_mode="HTML")


@router.message(Command("clearvocab"))
async def cmd_clearvocab(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    pool_repo: FromDishka[VocabPoolRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    user_id = message.from_user.id  # type: ignore
    profile = await profile_repo.get(user_id)
    if not profile:
        await message.answer(no_profile())
        return

    structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)
    logger.info("cmd_clearvocab", messenger_id=user_id)
    cleared = await pool_repo.clear_pool(profile.id, str(profile.target_lang))
    if cleared:
        await message.answer(
            f"♻️ Vocab pool cleared ({cleared} cards). Next /vocab will refill with fresh words."
        )
    else:
        await message.answer("Pool is already empty. /vocab will trigger a refill.")


@router.message(Command("help"))
async def cmd_help(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
) -> None:
    structlog.contextvars.clear_contextvars()
    profile = await profile_repo.get(message.from_user.id) if message.from_user else None
    if profile and message.from_user:
        structlog.contextvars.bind_contextvars(
            user_id=str(profile.id), messenger_id=message.from_user.id
        )
        logger.info("cmd_help", messenger_id=message.from_user.id)
    count = profile.vocab_card_count if profile else 8
    await message.answer(help_text(count), parse_mode="HTML")


@router.message(Command("bug"))
async def cmd_bug(message: Message, dialog_manager: DialogManager) -> None:
    await dialog_manager.start(BugSG.reporting, mode=StartMode.RESET_STACK)


@router.message(Command("exit"))
async def cmd_exit(message: Message) -> None:
    user_id = message.from_user.id  # type: ignore
    _pending_sessions.pop(user_id, None)
    _pending_writing.pop(user_id, None)
    # Import _pending_listening from listening module
    from src.infrastructure.telegram.handlers.listening import _pending_listening

    _pending_listening.pop(user_id, None)
    await message.answer(session_cancelled())


@router.message(_HasPendingSession())
async def handle_answer(
    message: Message,
    profile_repo: FromDishka[ProfileRepository],
    session_repo: FromDishka[SessionRepository],
    agent: FromDishka[LessonAgent],
) -> None:
    structlog.contextvars.clear_contextvars()
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

    response = f"📝 <b>Feedback:</b>\n\n{escape(feedback)}"

    # Offer writing exercise only if WRITING is in the user's strategy
    profile = await profile_repo.get(user_id)
    if profile is not None:
        structlog.contextvars.bind_contextvars(user_id=str(profile.id), messenger_id=user_id)
    logger.info("answer_received", messenger_id=user_id)
    writing_enabled = profile is None or ActivityType.WRITING in profile.learning_strategy

    if writing_enabled:
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
                    InlineKeyboardButton(
                        text="✍️ Sentences", callback_data=f"{_CB_WRITING}:sentences"
                    ),
                    InlineKeyboardButton(text="📝 Grammar", callback_data=f"{_CB_WRITING}:grammar"),
                    InlineKeyboardButton(
                        text="📰 Essay text", callback_data=f"{_CB_WRITING}:article"
                    ),
                ]
            ]
        )
        await message.answer(response, parse_mode="HTML", reply_markup=writing_kb)
    else:
        await message.answer(response, parse_mode="HTML")

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
    if profile is not None:
        await session_repo.save(session, profile.id)


@router.callback_query(F.data.startswith(f"{_CB_WRITING}:"))
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


@router.callback_query(F.data.startswith(f"{_CB_DEL_CARD}:"))
async def handle_delete_card(
    callback: CallbackQuery,
    agent: FromDishka[LessonAgent],
) -> None:
    user_id = callback.from_user.id
    cards = _last_cards.get(user_id, [])
    action = callback.data.split(":", 1)[1]  # type: ignore

    gateway: ICardGateway = agent._card_gateway

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


@catch_all_router.message(F.text)
async def handle_unknown(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is not None:
        return
    await message.answer(unknown_message())
