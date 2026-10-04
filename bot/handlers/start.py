from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.database.db import Database
from bot.keyboards.keyboards import (
    back_to_menu_keyboard,
    difficulty_keyboard,
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


def help_text() -> str:
    return (
        "🎮 <b>راهنمای بازی دوز</b>\n\n"
        "برای بازی با ربات، «بازی با هوش مصنوعی» را انتخاب و سطح را مشخص کنید.\n"
        "برای بازی گروهی، دستور /game را در گروه بفرستید؛ دو بازیکن با زدن "
        "دکمهٔ ورود وارد بازی می‌شوند. فقط بازیکنان و فقط در نوبت خودشان "
        "می‌توانند حرکت کنند.\n\n"
        "دستورها: /start، /game، /profile، /help"
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


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(help_text(), parse_mode="HTML")


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


@router.callback_query(F.data == "menu:help")
async def menu_help(query: CallbackQuery) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(
            help_text(),
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
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
async def menu_contact(query: CallbackQuery, admin_id: int) -> None:
    await query.answer()
    if query.message:
        await query.message.edit_text(
            '<a href="https://t.me/moein_915">💬 ورود به پیوی سازنده</a>',
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
