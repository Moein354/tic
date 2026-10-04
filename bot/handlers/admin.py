from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.database.db import Database
from bot.handlers.start import main_menu_text, profile_text
from bot.keyboards.keyboards import (
    admin_menu,
    admin_players_keyboard,
    admin_profile_keyboard,
    history_keyboard,
    main_menu,
)

router = Router(name="admin")
admin_waiting: set[int] = set()


def _is_admin(user_id: int, admin_id: int) -> bool:
    return user_id == admin_id


def _private_chat_link(user: dict) -> str:
    if user["username"]:
        url = f"https://t.me/{escape(user['username'], quote=True)}"
        return f'<a href="{url}">باز کردن پیوی</a>'
    return f'<a href="tg://user?id={user["user_id"]}">تلاش برای باز کردن پیوی</a>'


@router.message(Command("admin"))
async def admin_command(message: Message, admin_id: int) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, admin_id):
        await message.answer("⛔ دسترسی به پنل مدیریت ندارید.")
        return
    await message.answer("🛠 پنل مدیریت\n\nیک گزینه را انتخاب کنید:", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:panel")
async def admin_panel(query: CallbackQuery, admin_id: int) -> None:
    if not _is_admin(query.from_user.id, admin_id):
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    await query.answer()
    if query.message:
        await query.message.edit_text(
            "🛠 <b>پنل مدیریت</b>\n\nیک گزینه را انتخاب کنید:",
            parse_mode="HTML",
            reply_markup=admin_menu(),
        )


@router.callback_query(F.data.startswith("admin:players:"))
async def admin_players(query: CallbackQuery, db: Database, admin_id: int) -> None:
    if not _is_admin(query.from_user.id, admin_id):
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    raw_page = (query.data or "").rsplit(":", 1)[-1]
    if not raw_page.isdigit():
        await query.answer("شمارهٔ صفحه نامعتبر است.", show_alert=True)
        return
    page = int(raw_page)
    users, total = await db.list_played_users(page, exclude_user_id=admin_id)
    if page > 0 and not users:
        await query.answer("این صفحه وجود ندارد.", show_alert=True)
        return
    lines = ["👥 <b>بازیکنان ثبت‌شده</b>"]
    for index, user in enumerate(users, page * 5 + 1):
        username = f"@{escape(user['username'])}" if user["username"] else "ندارد"
        lines.append(
            f"\n{index}. 👤 <a href=\"tg://user?id={user['user_id']}\">"
            f"{escape(user['first_name'])}</a> ({username})"
            f"\n🆔 شناسه: <code>{user['user_id']}</code>"
            f"\n⭐ امتیاز: {user['rating']} | 🎮 بازی: {user['games_played']}"
            f"\n💬 {_private_chat_link(user)}"
        )
    if total == 0:
        lines.append("\nهنوز بازیکنی بازی نکرده است.")
    await query.answer()
    if query.message:
        await query.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=admin_players_keyboard(users, page, total),
        )


@router.callback_query(F.data == "admin:home")
async def admin_home(query: CallbackQuery, admin_id: int) -> None:
    if not _is_admin(query.from_user.id, admin_id):
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    await query.answer()
    if query.message:
        await query.message.edit_text(
            main_menu_text(query.from_user.first_name),
            reply_markup=main_menu(is_admin=True),
        )


@router.callback_query(F.data == "admin:search")
async def admin_search(query: CallbackQuery, admin_id: int) -> None:
    if not _is_admin(query.from_user.id, admin_id):
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    admin_waiting.add(query.from_user.id)
    await query.answer()
    if query.message:
        await query.message.answer("شناسهٔ عددی کاربر را ارسال کنید:")


@router.message(F.text, lambda message: bool(message.from_user and message.from_user.id in admin_waiting))
async def admin_user_id(message: Message, db: Database, admin_id: int) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, admin_id):
        return
    raw_id = (message.text or "").strip()
    if not raw_id.isdigit():
        await message.answer("شناسه باید فقط شامل عدد باشد. دوباره ارسال کنید:")
        return
    admin_waiting.discard(message.from_user.id)
    user = await db.get_user(int(raw_id))
    if not user:
        await message.answer("کاربری با این شناسه در آمار ربات پیدا نشد.")
        return
    username = f"@{escape(user['username'])}" if user["username"] else "ندارد"
    await message.answer(
        f"{profile_text(user)}\n👤 Username: {username}\n💬 {_private_chat_link(user)}",
        parse_mode="HTML",
        reply_markup=admin_profile_keyboard(user["user_id"], user["username"]),
    )


@router.callback_query(F.data.startswith("admin:user:"))
async def admin_user_callback(query: CallbackQuery, db: Database, admin_id: int) -> None:
    if not _is_admin(query.from_user.id, admin_id):
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    raw_id = (query.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await query.answer("شناسه نامعتبر است.", show_alert=True)
        return
    user = await db.get_user(int(raw_id))
    await query.answer()
    if user and query.message:
        username = f"@{escape(user['username'])}" if user["username"] else "ندارد"
        await query.message.edit_text(
            f"{profile_text(user)}\n👤 Username: {username}\n💬 {_private_chat_link(user)}",
            parse_mode="HTML",
            reply_markup=admin_profile_keyboard(user["user_id"], user["username"]),
        )



@router.callback_query(F.data.startswith("admin:history:"))
async def admin_history(query: CallbackQuery, db: Database, admin_id: int) -> None:
    if not _is_admin(query.from_user.id, admin_id):
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    parts = (query.data or "").split(":")
    if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit():
        await query.answer("درخواست نامعتبر است.", show_alert=True)
        return
    user_id, page = int(parts[2]), int(parts[3])
    rows, total = await db.get_history(user_id, page)
    if not rows and page:
        await query.answer("صفحه‌ای با این شماره وجود ندارد.", show_alert=True)
        return
    labels = {"win": "🏆 برد", "loss": "❌ باخت", "draw": "🤝 مساوی"}
    lines = [f"📜 <b>تاریخچهٔ بازی‌های {user_id}</b>"]
    for index, game in enumerate(rows, page * 5 + 1):
        delta = f"+{game['delta']}" if game["delta"] > 0 else str(game["delta"])
        played_at = game["played_at"].replace("T", " ")[:16]
        lines.append(
            f"\n{index}. {labels[game['result']]} مقابل {escape(game['opponent_name'])} "
            f"— {delta}\n   نقش {game['role']} | "
            f"{game['score_before']} → {game['score_after']} | {played_at} UTC"
        )
    if total == 0:
        lines.append("\nهنوز سابقه‌ای ثبت نشده است.")
    await query.answer()
    if query.message:
        await query.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=history_keyboard(user_id, page, total),
        )
