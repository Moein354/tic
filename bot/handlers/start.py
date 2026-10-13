from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.database.db import Database
from bot.keyboards.keyboards import (
    back_to_menu_keyboard,
    difficulty_keyboard,
    leaderboard_keyboard,
    main_menu,
)

router = Router(name="start")


def main_menu_text(first_name: str) -> str:
    return (
        f"سلام {escape(first_name)}\n"
        "به ربات دوز خوش آمدید از منوی زیر یک گزینه را انتخاب کنید"
    )


def _total(user: dict) -> int:
    return user["wins"] + user["losses"] + user["draws"]


def profile_text(user: dict) -> str:
    total = _total(user)
    percentage = user["wins"] * 100 / total if total else 0
    return (
        f"👤 نام: {escape(user['first_name'])}\n"
        f"🆔 آیدی عددی: <code>{user['user_id']}</code>\n"
        f"🎮 تعداد بازی‌ها: {total}\n"
        f"🏆 بردها: {user['wins']}\n"
        f"💔 باخت‌ها: {user['losses']}\n"
        f"🤝 مساوی‌ها: {user['draws']}\n"
        f"⭐ امتیاز: {user['rating']}\n"
        f"📊 درصد برد: {percentage:.1f}%"
    )


@router.message(Command("start"))
async def start_command(message: Message, db: Database, admin_id: int) -> None:
    if not message.from_user:
        return
    await db.ensure_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    is_admin = message.from_user.id == admin_id
    await message.answer(
        main_menu_text(message.from_user.first_name),
        reply_markup=main_menu(is_admin),
    )


@router.message(Command("profile"))
async def profile_command(message: Message, db: Database) -> None:
    if not message.from_user:
        return
    user = message.from_user
    await db.ensure_user(user.id, user.username, user.first_name)
    record = await db.get_user(user.id)
    if record:
        await message.answer(profile_text(record), parse_mode="HTML")


@router.callback_query(F.data == "menu:ai")
async def choose_ai_level(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(
            "🤖 <b>بازی با هوش مصنوعی</b>\n\nسطح بازی را انتخاب کنید:",
            reply_markup=difficulty_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "menu:home")
async def menu_home(query: CallbackQuery, admin_id: int) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(
            main_menu_text(query.from_user.first_name),
            reply_markup=main_menu(query.from_user.id == admin_id),
        )


@router.callback_query(F.data == "ai:levels")
async def ai_levels(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(
            "🤖 <b>بازی با هوش مصنوعی</b>\n\nسطح بازی را انتخاب کنید:",
            reply_markup=difficulty_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "menu:profile")
async def menu_profile(query: CallbackQuery, db: Database) -> None:
    await query.answer()
    if not query.from_user:
        return
    user = query.from_user
    await db.ensure_user(user.id, user.username, user.first_name)
    record = await db.get_user(user.id)
    if record and query.message:
        await query.message.edit_text(
            profile_text(record),
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )


@router.callback_query(F.data.startswith("menu:leaderboard"))
async def menu_leaderboard(query: CallbackQuery, db: Database) -> None:
    parts = (query.data or "").split(":")
    if len(parts) < 2 or parts[1] != "leaderboard":
        await query.answer("درخواست نامعتبر است.", show_alert=True)
        return
    if len(parts) == 2:
        page = 0
    elif len(parts) == 3 and parts[2].isdigit():
        page = int(parts[2])
    else:
        await query.answer("شمارهٔ صفحه نامعتبر است.", show_alert=True)
        return

    users, total = await db.list_played_users(page, page_size=5)
    if page > 0 and not users:
        await query.answer("این صفحه وجود ندارد.", show_alert=True)
        return
    personal_rank = await db.get_played_user_rank(query.from_user.id)

    lines = ["🏆 <b>برترین بازیکنان</b>\n⭐ امتیاز: برد ۵۰ | مساوی ۲۵ | باخت ۰"]
    medals = ("🥇", "🥈", "🥉")
    for index, user in enumerate(users, page * 5 + 1):
        rank = medals[index - 1] if index <= len(medals) else f"{index}."
        lines.append(
            f"\n{rank} <a href=\"tg://user?id={user['user_id']}\">"
            f"{escape(user['first_name'])}</a>"
            f" — ⭐ {user['rating']} امتیاز"
            f"\n   🏆 {user['wins']} برد | 🤝 {user['draws']} مساوی"
            f" | ❌ {user['losses']} باخت"
        )
    if total == 0:
        lines.append("\nهنوز بازی‌ای ثبت نشده است.")
    if personal_rank:
        lines.append(
            f"\n👤 <b>رتبهٔ شما:</b> {personal_rank['rank']} از {total}"
            f" — ⭐ {personal_rank['rating']} امتیاز"
        )
    else:
        lines.append("\n👤 <b>رتبهٔ شما:</b> هنوز بازی‌ای ثبت نکرده‌اید.")

    await query.answer()
    if query.message:
        await query.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=leaderboard_keyboard(page, total),
        )


@router.callback_query(F.data == "menu:about")
async def menu_about(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(
            "داداش نخبم من",
            reply_markup=back_to_menu_keyboard(),
        )


@router.callback_query(F.data == "menu:contact")
async def menu_contact(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(
            '<a href="https://t.me/moein_915">💬 ورود به پیوی سازنده</a>',
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
