import asyncio
import logging
import uuid
from collections import defaultdict, deque
from html import escape
import aiosqlite
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    ChosenInlineResult,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
    User,
)

from bot.database.db import Database
from bot.game.ai import choose_move
from bot.game.engine import AiGame, GroupGame, is_draw, winner
from bot.handlers.start import main_menu_text
from bot.keyboards.keyboards import (
    ai_finished_keyboard,
    board_keyboard,
    ai_symbol_keyboard,
    difficulty_keyboard,
    inline_join_keyboard,
    join_keyboard,
    main_menu,
)

router = Router(name="games")
logger = logging.getLogger(__name__)
group_games: dict[int, GroupGame] = {}
inline_games: dict[str, GroupGame] = {}
ai_games: dict[int, AiGame] = {}
ai_choice_history: dict[tuple[int, str, str, tuple], deque[int]] = defaultdict(
    lambda: deque(maxlen=8)
)
group_creation_lock = asyncio.Lock()
inline_creation_lock = asyncio.Lock()
bot_username = ""


def set_bot_username(username: str) -> None:
    global bot_username
    bot_username = username.casefold()


def _mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{escape(name)}</a>'


def _display_name(user: User) -> str:
    return " ".join(part for part in (user.first_name, user.last_name) if part)


def _choose_ai_move(game: AiGame) -> int:
    position = (
        game.user_id,
        game.difficulty,
        game.ai_mark,
        tuple(game.board),
    )
    history = ai_choice_history[position]
    move = choose_move(
        game.board,
        game.difficulty,
        game.ai_mark,
        recent_moves=tuple(history),
    )
    history.append(move)
    return move


def _group_caption(game: GroupGame) -> str:
    if game.status == "waiting":
        if game.x_id is None and game.o_id is None:
            return "🎮 <b>بازی دوز</b>\n\nبرای شروع بازی روی دکمهٔ زیر بزنید؛ دو نفر اول وارد بازی می‌شوند."
        players = []
        if game.x_id is not None:
            players.append(f"❌ بازیکن X: {_mention(game.x_id, game.x_name or 'بازیکن')}")
        if game.o_id is not None:
            players.append(f"⭕ بازیکن O: {_mention(game.o_id, game.o_name or 'بازیکن')}")
        return "🎮 <b>بازی دوز</b>\n\n" + "\n".join(players) + "\n⏳ منتظر بازیکن دوم..."
    return (
        "🎮 <b>بازی دوز</b>\n"
        "👥 <b>بازیکنان:</b>\n"
        f"❌ X: {_mention(game.x_id or 0, game.x_name or 'بازیکن')}\n"
        f"⭕ O: {_mention(game.o_id or 0, game.o_name or 'بازیکن')}\n\n"
        f"🎮 بازی شروع شد\nنوبت {'❌' if game.turn == 'X' else '⭕'} "
        f"{_mention(game.x_id if game.turn == 'X' else game.o_id or 0, game.x_name if game.turn == 'X' else game.o_name or 'بازیکن')}"
    )


async def _create_group_game(message: Message) -> None:
    if not message.chat or not message.from_user:
        return
    chat_id = message.chat.id
    async with group_creation_lock:
        current = group_games.get(chat_id)
        if current and current.status != "finished":
            await message.reply("⏳ در این گروه یک بازی در حال انتظار یا اجراست.")
            return
        game_id = uuid.uuid4().hex
        sent = await message.answer(
            "🎮 <b>بازی دوز</b>\n\nبرای شروع بازی روی دکمهٔ زیر بزنید؛ دو نفر اول وارد بازی می‌شوند.",
            reply_markup=join_keyboard(game_id),
            parse_mode="HTML",
        )
        group_games[chat_id] = GroupGame(
            game_id=game_id, chat_id=chat_id, message_id=sent.message_id
        )


async def _edit_game_message(
    query: CallbackQuery, game: GroupGame, text: str, keyboard=None
) -> None:
    if query.message:
        await query.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    elif game.inline_message_id:
        await query.bot.edit_message_text(
            text,
            inline_message_id=game.inline_message_id,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


def _restore_inline_game(data: dict) -> GroupGame:
    return GroupGame(
        game_id=data["game_id"],
        chat_id=None,
        message_id=None,
        inline_message_id=data["inline_message_id"],
        board=data["board"],
        x_id=data["x_id"],
        x_name=data["x_name"],
        o_id=data["o_id"],
        o_name=data["o_name"],
        turn=data["turn"],
        status=data["status"],
    )


def _inline_game_owner(game_id: str) -> tuple[str, int] | None:
    parts = game_id.split("_")
    if (
        len(parts) != 3
        or parts[0] not in ("x", "o")
        or not parts[1].isdigit()
        or len(parts[2]) not in (12, 32)
    ):
        return None
    try:
        int(parts[2], 16)
        owner_id = int(parts[1])
    except ValueError:
        return None
    return parts[0].upper(), owner_id


def _truncate_utf8(value: str, max_bytes: int) -> str:
    encoded = value.encode("utf-8")[:max_bytes]
    return encoded.decode("utf-8", errors="ignore")


@router.inline_query()
async def inline_game_search(query: InlineQuery) -> None:
    results = []
    owner = query.from_user
    for mark, symbol in (("X", "❌"), ("O", "⭕")):
        result_id = f"{mark.lower()}_{owner.id}_{uuid.uuid4().hex[:12]}"
        results.append(
            InlineQueryResultArticle(
                id=result_id,
                title=f"{symbol} شروع بازی با {mark}",
                description=f"بازی دوز دونفره؛ شما با مهرهٔ {mark} بازی می‌کنید",
                input_message_content=InputTextMessageContent(
                    message_text=f"🎮 <b>بازی دوز — شروع‌کننده با {symbol} {mark}</b>",
                    parse_mode="HTML",
                ),
                reply_markup=inline_join_keyboard(result_id, _display_name(owner)),
            )
        )
    await query.answer(
        results=results,
        cache_time=0,
        is_personal=True,
    )


@router.chosen_inline_result()
async def create_selected_inline_game(
    result: ChosenInlineResult, db: Database
) -> None:
    game_id = result.result_id
    parsed_game = _inline_game_owner(game_id)
    if parsed_game is None:
        logger.warning("Ignoring inline result with invalid game id %s", game_id)
        return
    if not result.inline_message_id:
        return

    user = result.from_user
    mark, owner_id = parsed_game
    if user.id != owner_id:
        logger.error("Inline result owner mismatch for game %s", game_id)
        return
    display_name = _display_name(user)
    await db.ensure_user(user.id, user.username, user.first_name)
    async with inline_creation_lock:
        try:
            saved_game = await db.get_inline_game(game_id)
            if saved_game:
                if saved_game["inline_message_id"] == result.inline_message_id:
                    game = _restore_inline_game(saved_game)
                    if mark == "X" and game.x_id == user.id:
                        game.x_name = display_name
                    elif mark == "O" and game.o_id == user.id:
                        game.o_name = display_name
                    await db.save_inline_game(game)
                    inline_games[game_id] = game
                    return
                logger.warning("Inline game id %s is already assigned to another message", game_id)
                return
            active_game = await db.get_active_inline_game(result.inline_message_id)
            if active_game:
                logger.warning(
                    "An active inline game already exists for message %s",
                    result.inline_message_id,
                )
                return
            game = GroupGame(
                game_id=game_id,
                chat_id=None,
                message_id=None,
                inline_message_id=result.inline_message_id,
                x_id=user.id if mark == "X" else None,
                x_name=display_name if mark == "X" else None,
                o_id=user.id if mark == "O" else None,
                o_name=display_name if mark == "O" else None,
            )
            await db.save_inline_game(game)
        except aiosqlite.Error:
            logger.exception("Failed to persist selected inline game %s", game_id)
            return
        inline_games[game_id] = game


@router.message(Command("game"))
async def game_command(message: Message) -> None:
    if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        await _create_group_game(message)
    else:
        await message.answer(
            "برای بازی با هوش مصنوعی یک سطح را انتخاب کنید:",
            reply_markup=difficulty_keyboard(),
        )


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text)
async def mention_bot(message: Message) -> None:
    if not bot_username or not message.text or message.text.startswith("/"):
        return
    bot_tag = f"@{bot_username}"
    mentioned = any(
        entity.type == "mention"
        and message.text[entity.offset : entity.offset + entity.length].casefold() == bot_tag
        for entity in (message.entities or [])
    )
    if mentioned:
        await _create_group_game(message)


@router.callback_query(F.data.startswith("gj:"))
async def join_group_game(query: CallbackQuery, db: Database) -> None:
    game_id = (query.data or "").partition(":")[2]
    game = next((item for item in group_games.values() if item.game_id == game_id), None)
    if game is None or not query.from_user:
        await query.answer("این بازی دیگر در دسترس نیست.", show_alert=True)
        return
    user = query.from_user
    await db.ensure_user(user.id, user.username, user.first_name)
    async with game.lock:
        if (
            not query.message
            or game.chat_id is None
            or query.message.chat.id != game.chat_id
            or query.message.message_id != game.message_id
        ):
            await query.answer("این دکمه متعلق به پیام بازی نیست.", show_alert=True)
            return
        if game.status != "waiting":
            await query.answer("این بازی شروع شده یا پایان یافته است.", show_alert=True)
            return
        if game.x_id == user.id:
            await query.answer("شما بازیکن X هستید؛ منتظر بازیکن دوم بمانید.", show_alert=True)
            return
        if game.x_id is None:
            game.x_id, game.x_name = user.id, user.first_name
            await query.answer("شما بازیکن X هستید؛ منتظر بازیکن دوم بمانید.")
            if query.message:
                await query.message.edit_text(
                    _group_caption(game), reply_markup=join_keyboard(game.game_id), parse_mode="HTML"
                )
            return
        game.o_id, game.o_name = user.id, user.first_name
        game.status, game.turn = "playing", "X"
        await query.answer("بازی شروع شد")
        if query.message:
            await query.message.edit_text(
                _group_caption(game),
                reply_markup=board_keyboard(game.board, game.game_id),
                parse_mode="HTML",
            )


@router.callback_query(F.data.startswith("is:"))
async def start_inline_game(query: CallbackQuery, db: Database) -> None:
    parts = (query.data or "").split(":")
    if not query.from_user or not query.inline_message_id:
        await query.answer("این دکمه فقط در پیام inline قابل استفاده است.", show_alert=True)
        return
    if len(parts) == 2:
        mark = "X"
    elif len(parts) == 3 and parts[2] in ("X", "O"):
        mark = parts[2]
    else:
        await query.answer("انتخاب مهره نامعتبر است.", show_alert=True)
        return
    user = query.from_user
    await db.ensure_user(user.id, user.username, user.first_name)
    async with inline_creation_lock:
        current = await db.get_active_inline_game(query.inline_message_id)
        if current:
            await query.answer("در این پیام یک بازی در حال اجراست.", show_alert=True)
            return
        game_id = uuid.uuid4().hex
        game = GroupGame(
            game_id=game_id,
            chat_id=None,
            message_id=None,
            inline_message_id=query.inline_message_id,
            x_id=user.id if mark == "X" else None,
            x_name=user.first_name if mark == "X" else None,
            o_id=user.id if mark == "O" else None,
            o_name=user.first_name if mark == "O" else None,
        )
        try:
            await db.save_inline_game(game)
        except aiosqlite.Error:
            logger.exception("Failed to persist inline game %s", game_id)
            await query.answer("ساخت بازی ناموفق بود؛ دوباره تلاش کنید.", show_alert=True)
            return
        inline_games[game_id] = game
    await query.answer(f"شما بازیکن {mark} هستید؛ منتظر بازیکن دوم بمانید.")
    await _edit_game_message(
        query, game, _group_caption(game), inline_join_keyboard(game_id, _display_name(user))
    )


@router.callback_query(F.data.startswith("ii:"))
async def join_inline_game(query: CallbackQuery, db: Database) -> None:
    callback_data = (query.data or "").partition(":")[2]
    game_id, _, owner_name = callback_data.partition(":")
    if not query.from_user or not query.inline_message_id:
        await query.answer("این دکمه فقط در پیام inline قابل استفاده است.", show_alert=True)
        return
    user = query.from_user
    game = inline_games.get(game_id)
    if game is None:
        try:
            saved_game = await db.get_inline_game(game_id)
            if saved_game:
                game = _restore_inline_game(saved_game)
                inline_games[game_id] = game
            else:
                owner_data = _inline_game_owner(game_id)
                if owner_data is not None:
                    mark, owner_id = owner_data
                    async with inline_creation_lock:
                        # Recheck after acquiring the lock in case another callback initialized it.
                        saved_game = await db.get_inline_game(game_id)
                        if saved_game:
                            game = _restore_inline_game(saved_game)
                        elif not await db.get_active_inline_game(query.inline_message_id):
                            game = GroupGame(
                                game_id=game_id,
                                chat_id=None,
                                message_id=None,
                                inline_message_id=query.inline_message_id,
                                x_id=owner_id if mark == "X" else None,
                                x_name=owner_name or "بازیکن" if mark == "X" else None,
                                o_id=owner_id if mark == "O" else None,
                                o_name=owner_name or "بازیکن" if mark == "O" else None,
                            )
                            await db.save_inline_game(game)
                        if game:
                            inline_games[game_id] = game
        except aiosqlite.Error:
            logger.exception("Failed to initialize inline game %s", game_id)
            await query.answer("ساخت بازی ناموفق بود؛ دوباره تلاش کنید.", show_alert=True)
            return
    if game is None:
        await query.answer("این بازی inline دیگر در دسترس نیست.", show_alert=True)
        return
    display_name = _display_name(user)
    await db.ensure_user(user.id, user.username, user.first_name)
    async with game.lock:
        if game.inline_message_id != query.inline_message_id:
            await query.answer("این دکمه متعلق به پیام بازی دیگری است.", show_alert=True)
            return
        if game.status != "waiting":
            await query.answer("این بازی شروع شده یا پایان یافته است.", show_alert=True)
            return
        if user.id in (game.x_id, game.o_id):
            mark = "X" if game.x_id == user.id else "O"
            await query.answer(
                f"شما بازیکن {mark} هستید؛ منتظر بازیکن دوم بمانید.",
                show_alert=True,
            )
            return
        previous_players = (game.x_id, game.x_name, game.o_id, game.o_name)
        if game.x_id is None:
            game.x_id, game.x_name = user.id, display_name
        else:
            game.o_id, game.o_name = user.id, display_name
        game.status, game.turn = "playing", "X"
        try:
            await db.save_inline_game(game)
        except aiosqlite.Error:
            game.x_id, game.x_name, game.o_id, game.o_name = previous_players
            game.status = "waiting"
            logger.exception("Failed to persist inline game join %s", game_id)
            await query.answer("ورود به بازی ذخیره نشد؛ دوباره تلاش کنید.", show_alert=True)
            return
        await query.answer("بازی شروع شد")
        await _edit_game_message(
            query,
            game,
            _group_caption(game),
            board_keyboard(game.board, game.game_id),
        )


@router.callback_query(F.data.startswith("ai:"))
async def start_ai_game(query: CallbackQuery, db: Database) -> None:
    difficulty = (query.data or "").partition(":")[2]
    if difficulty not in ("easy", "medium", "expert") or not query.from_user or not query.message:
        await query.answer("انتخاب سطح نامعتبر است.", show_alert=True)
        return
    await query.answer()
    await query.message.edit_text(
        "دوست دارید با کدام مهره بازی کنید؟",
        reply_markup=ai_symbol_keyboard(difficulty),
    )


@router.callback_query(F.data.startswith("aisym:"))
async def start_ai_game_with_symbol(
    query: CallbackQuery, db: Database
) -> None:
    parts = (query.data or "").split(":")
    if (
        len(parts) != 3
        or parts[1] not in ("easy", "medium", "expert")
        or parts[2] not in ("X", "O")
        or not query.from_user
        or not query.message
    ):
        await query.answer("انتخاب سطح یا مهره نامعتبر است.", show_alert=True)
        return
    difficulty, human_mark = parts[1], parts[2]
    user = query.from_user
    await db.ensure_user(user.id, user.username, user.first_name)
    current = ai_games.get(user.id)
    if current and current.status == "playing":
        await query.answer("ابتدا بازی فعلی خود را تمام کنید.", show_alert=True)
        return
    game = AiGame(
        uuid.uuid4().hex,
        user.id,
        user.first_name,
        difficulty,
        human_mark=human_mark,
    )
    if human_mark == "O":
        game.board[_choose_ai_move(game)] = game.ai_mark
    ai_games[user.id] = game
    labels = {"easy": "آسان", "medium": "متوسط", "expert": "حرفه‌ای"}
    await query.answer()
    await query.message.edit_text(
        _ai_board_text(game, labels[difficulty]),
        reply_markup=board_keyboard(
            game.board,
            game.game_id,
            allow_back=True,
        ),
        parse_mode="HTML",
    )


def _ai_board_text(game: AiGame, difficulty_label: str) -> str:
    intro = (
        "اولین حرکت با شماست."
        if game.human_mark == "X"
        else f"هوش مصنوعی با ❌ X شروع کرد؛ نوبت شماست."
    )
    return (
        f"🤖 <b>بازی با هوش مصنوعی — سطح {difficulty_label}</b>\n"
        f"شما {'❌ X' if game.human_mark == 'X' else '⭕ O'} هستید.\n"
        f"{intro}"
    )


@router.callback_query(F.data.startswith("aiback:"))
async def leave_ai_game(query: CallbackQuery, admin_id: int) -> None:
    game_id = (query.data or "").partition(":")[2]
    game = ai_games.get(query.from_user.id)
    if game is None or game.game_id != game_id:
        await query.answer("این بازی برای شما فعال نیست.", show_alert=True)
        return
    async with game.lock:
        if game.status == "playing":
            game.status = "cancelled"
    await query.answer()
    if query.message:
        await query.message.edit_text(
            main_menu_text(query.from_user.first_name),
            reply_markup=main_menu(query.from_user.id == admin_id),
        )


@router.callback_query(F.data.startswith("aireplay:"))
async def replay_ai_game(query: CallbackQuery) -> None:
    game_id = (query.data or "").partition(":")[2]
    if not query.from_user or not query.message:
        await query.answer("این بازی برای شما در دسترس نیست.", show_alert=True)
        return
    previous_game = ai_games.get(query.from_user.id)
    if (
        previous_game is None
        or previous_game.game_id != game_id
        or previous_game.status != "finished"
    ):
        await query.answer("این بازی دیگر قابل تکرار نیست.", show_alert=True)
        return

    async with previous_game.lock:
        if previous_game.status != "finished":
            await query.answer("این بازی هنوز پایان نیافته است.", show_alert=True)
            return
        game = AiGame(
            uuid.uuid4().hex,
            previous_game.user_id,
            previous_game.user_name,
            previous_game.difficulty,
            human_mark=previous_game.human_mark,
        )
        if game.human_mark == "O":
            ai_move = _choose_ai_move(game)
            game.board[ai_move] = game.ai_mark
        ai_games[game.user_id] = game

    labels = {"easy": "آسان", "medium": "متوسط", "expert": "حرفه‌ای"}
    await query.answer("بازی جدید شروع شد")
    await query.message.edit_text(
        _ai_board_text(game, labels[game.difficulty]),
        reply_markup=board_keyboard(
            game.board,
            game.game_id,
            allow_back=True,
        ),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("aimenu:"))
async def ai_game_main_menu(query: CallbackQuery, admin_id: int) -> None:
    parts = (query.data or "").split(":")
    game_id = parts[1] if len(parts) > 1 else ""
    game = ai_games.get(query.from_user.id)
    if game is None or game.game_id != game_id or game.status != "finished":
        await query.answer("این دکمه دیگر معتبر نیست.", show_alert=True)
        return
    await query.answer()
    if query.message:
        await query.message.edit_text(
            main_menu_text(query.from_user.first_name),
            reply_markup=main_menu(query.from_user.id == admin_id),
        )


def _ai_finish_text(game: AiGame, outcome: str, delta: int) -> str:
    if outcome == game.human_mark:
        result = "🏆 شما برنده شدید"
    elif outcome == game.ai_mark:
        result = (
            "🤖 هوش مصنوعی برنده شد\n"
            f"😄 این بار باختی به من، {escape(game.user_name)}. "
            "اشکالی ندارد، دور بعد جبران کن"
        )
    else:
        result = "🤝 بازی مساوی شد"
    signed = f"+{delta}" if delta > 0 else str(delta)
    return f"{result}\n\n⭐ امتیاز شما: {signed}"


@router.callback_query(F.data.startswith("b:"))
async def play_move(
    query: CallbackQuery, db: Database, admin_id: int
) -> None:
    parts = (query.data or "").split(":")
    if len(parts) != 3 or not parts[2].isdigit() or not query.from_user:
        await query.answer("حرکت نامعتبر است.", show_alert=True)
        return
    _, game_id, raw_index = parts
    index = int(raw_index)
    if index > 8:
        await query.answer("خانهٔ انتخاب‌شده معتبر نیست.", show_alert=True)
        return
    user_id = query.from_user.id
    group_game = next((item for item in group_games.values() if item.game_id == game_id), None)
    inline_game = inline_games.get(game_id)
    if inline_game is None and group_game is None:
        try:
            saved_game = await db.get_inline_game(game_id)
        except aiosqlite.Error:
            logger.exception("Failed to load inline game for move %s", game_id)
            await query.answer("بازی در دسترس نیست؛ دوباره تلاش کنید.", show_alert=True)
            return
        if saved_game:
            inline_game = _restore_inline_game(saved_game)
            inline_games[game_id] = inline_game
    active_game = group_game or inline_game
    if active_game:
        async with active_game.lock:
            if active_game.inline_message_id is not None:
                if query.inline_message_id != active_game.inline_message_id:
                    await query.answer("این دکمه متعلق به پیام بازی دیگری است.", show_alert=True)
                    return
            elif (
                not query.message
                or active_game.chat_id is None
                or query.message.chat.id != active_game.chat_id
                or query.message.message_id != active_game.message_id
            ):
                await query.answer("این دکمه متعلق به پیام بازی نیست.", show_alert=True)
                return
            if active_game.status != "playing":
                await query.answer("این بازی فعال نیست.", show_alert=True)
                return
            role = "X" if user_id == active_game.x_id else "O" if user_id == active_game.o_id else None
            if role is None:
                await query.answer("فقط بازیکنان این بازی می‌توانند حرکت کنند.", show_alert=True)
                return
            if role != active_game.turn:
                await query.answer("الان نوبت شما نیست.", show_alert=True)
                return
            if active_game.board[index] is not None:
                await query.answer("این خانه قبلاً انتخاب شده است.", show_alert=True)
                return
            previous_turn = active_game.turn
            active_game.board[index] = role
            game_winner = winner(active_game.board)
            draw = is_draw(active_game.board)
            if game_winner or draw:
                outcome = game_winner or "draw"
                try:
                    deltas = await db.record_game(
                        game_id=active_game.game_id,
                        game_type="inline" if active_game.inline_message_id else "group",
                        group_id=active_game.chat_id,
                        x_id=active_game.x_id or 0,
                        o_id=active_game.o_id,
                        x_name=active_game.x_name or "X",
                        o_name=active_game.o_name or "O",
                        outcome=outcome,
                    )
                except aiosqlite.Error:
                    active_game.board[index] = None
                    logger.exception("Failed to save completed group game %s", game_id)
                    await query.answer("ذخیرهٔ نتیجه ناموفق بود؛ دوباره تلاش کنید.", show_alert=True)
                    return
                active_game.status = "finished"
                if active_game.inline_message_id:
                    try:
                        await db.save_inline_game(active_game)
                    except aiosqlite.Error:
                        logger.exception("Failed to persist finished inline game %s", game_id)
                if outcome == "draw":
                    text = (
                        "🤝 <b>بازی مساوی شد</b>\n\n"
                        "👥 بازیکنان:\n"
                        f"❌ X: {_mention(active_game.x_id or 0, active_game.x_name or 'بازیکن')}\n"
                        f"⭕ O: {_mention(active_game.o_id or 0, active_game.o_name or 'بازیکن')}"
                    )
                else:
                    win_id, win_name = (
                        (active_game.x_id, active_game.x_name)
                        if outcome == "X"
                        else (active_game.o_id, active_game.o_name)
                    )
                    lose_id, lose_name = (
                        (active_game.o_id, active_game.o_name)
                        if outcome == "X"
                        else (active_game.x_id, active_game.x_name)
                    )
                    text = (
                        "🏆 <b>بازی تمام شد</b>\n\n"
                        f"🏆 برنده: {_mention(win_id or 0, win_name or 'بازیکن')}\n"
                        f"❌ بازنده: {_mention(lose_id or 0, lose_name or 'بازیکن')}"
                    )
                text += (
                    "\n\n⭐ امتیاز:\n"
                    f"{_mention(active_game.x_id or 0, active_game.x_name or 'X')} → "
                    f"{deltas[active_game.x_id or 0]:+d}\n"
                    f"{_mention(active_game.o_id or 0, active_game.o_name or 'O')} → "
                    f"{deltas[active_game.o_id or 0]:+d}"
                )
                await query.answer()
                await _edit_game_message(query, active_game, text)
                return
            active_game.turn = "O" if role == "X" else "X"
            if active_game.inline_message_id:
                try:
                    await db.save_inline_game(active_game)
                except aiosqlite.Error:
                    active_game.board[index] = None
                    active_game.turn = previous_turn
                    logger.exception("Failed to persist inline move %s", game_id)
                    await query.answer("حرکت ذخیره نشد؛ دوباره تلاش کنید.", show_alert=True)
                    return
            await query.answer()
            await _edit_game_message(
                query,
                active_game,
                _group_caption(active_game),
                board_keyboard(active_game.board, active_game.game_id),
            )
        return

    game = ai_games.get(user_id)
    if game is None or game.game_id != game_id:
        await query.answer("این بازی برای شما فعال نیست.", show_alert=True)
        return
    async with game.lock:
        if game.status != "playing":
            await query.answer("این بازی پایان یافته است.", show_alert=True)
            return
        if game.board[index] is not None:
            await query.answer("این خانه قبلاً انتخاب شده است.", show_alert=True)
            return
        previous_board = game.board.copy()
        game.board[index] = game.human_mark
        outcome = winner(game.board)
        if not outcome and not is_draw(game.board):
            ai_index = _choose_ai_move(game)
            game.board[ai_index] = game.ai_mark
            outcome = winner(game.board)
        draw = outcome is None and is_draw(game.board)
        if outcome or draw:
            result = outcome or "draw"
            try:
                deltas = await db.record_game(
                    game_id=game.game_id,
                    game_type=f"ai_{game.difficulty}",
                    group_id=None,
                    x_id=game.user_id if game.human_mark == "X" else 0,
                    o_id=game.user_id if game.human_mark == "O" else None,
                    x_name=game.user_name if game.human_mark == "X" else "هوش مصنوعی",
                    o_name="هوش مصنوعی" if game.human_mark == "X" else game.user_name,
                    outcome=result,
                    human_role=game.human_mark,
                )
            except aiosqlite.Error:
                game.board[:] = previous_board
                logger.exception("Failed to save completed AI game %s", game_id)
                await query.answer("ذخیرهٔ نتیجه ناموفق بود.", show_alert=True)
                return
            game.status = "finished"
            text = _ai_finish_text(game, result, deltas[game.user_id])
            await query.answer()
            if query.message:
                await query.message.edit_text(
                    text,
                    reply_markup=ai_finished_keyboard(
                        game.board,
                        game.game_id,
                        query.from_user.id == admin_id,
                    ),
                    parse_mode="HTML",
                )
            return
        await query.answer()
        if query.message:
            labels = {"easy": "آسان", "medium": "متوسط", "expert": "حرفه‌ای"}
            await query.message.edit_text(
                _ai_board_text(game, labels[game.difficulty]),
                reply_markup=board_keyboard(
                    game.board,
                    game.game_id,
                    allow_back=True,
                ),
            )
