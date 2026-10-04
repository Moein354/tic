from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎮 شروع بازی", callback_data="menu:ai", style="primary")],
        [InlineKeyboardButton(text="👤 پروفایل من", callback_data="menu:profile", style="primary")],
        [InlineKeyboardButton(text="ℹ️ راهنما", callback_data="menu:help", style="primary")],
    ]
    if is_admin:
        rows.append(
            [InlineKeyboardButton(text="🛠 پنل مدیریت", callback_data="admin:panel", style="primary")]
        )
    rows.append(
        [
            InlineKeyboardButton(text="👨‍💻 درباره سازنده", callback_data="menu:about", style="primary"),
            InlineKeyboardButton(
                text="💬 ارتباط با سازنده",
                url="https://t.me/moein_915",
                style="primary",
            ),
        ]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def difficulty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 آسان", callback_data="ai:easy", style="success")],
            [InlineKeyboardButton(text="🟡 متوسط", callback_data="ai:medium")],
            [InlineKeyboardButton(text="🔴 حرفه‌ای", callback_data="ai:expert", style="danger")],
            [InlineKeyboardButton(text="↩️ بازگشت به منوی اصلی", callback_data="menu:home", style="danger")],
        ]
    )


def ai_symbol_keyboard(difficulty: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ بازی با X", callback_data=f"aisym:{difficulty}:X", style="primary"),
                InlineKeyboardButton(text="⭕ بازی با O", callback_data=f"aisym:{difficulty}:O", style="primary"),
            ],
            [InlineKeyboardButton(text="↩️ بازگشت به انتخاب سطح", callback_data="ai:levels", style="danger")],
        ]
    )


def board_keyboard(
    board: list[Optional[str]], game_id: str, allow_back: bool = False
) -> InlineKeyboardMarkup:
    symbols = {None: "⬜", "X": "❌", "O": "⭕"}
    rows = []
    for row in range(3):
        rows.append(
            [
                InlineKeyboardButton(
                    text=symbols[board[index]],
                    callback_data=f"b:{game_id}:{index}",
                    style="primary",
                )
                for index in range(row * 3, row * 3 + 3)
            ]
        )
    if allow_back:
        rows.append(
            [InlineKeyboardButton(text="↩️ بازگشت به منو", callback_data=f"aiback:{game_id}", style="danger")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_finished_keyboard(
    board: list[Optional[str]], game_id: str, is_admin: bool = False
) -> InlineKeyboardMarkup:
    keyboard = board_keyboard(board, game_id).inline_keyboard
    keyboard.append(
        [
            InlineKeyboardButton(
                text="🔄 دوباره بازی کردن",
                callback_data=f"aireplay:{game_id}",
                style="primary",
            ),
            InlineKeyboardButton(
                text="🏠 منوی اصلی",
                callback_data=f"aimenu:{game_id}:{int(is_admin)}",
                style="danger",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ بازگشت به منوی اصلی", callback_data="menu:home", style="danger")]
        ]
    )


def join_keyboard(game_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 شروع بازی / ورود", callback_data=f"gj:{game_id}", style="primary")]
        ]
    )


def inline_join_keyboard(game_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 ورود به بازی", callback_data=f"ii:{game_id}", style="primary")]
        ]
    )


def inline_start_keyboard(result_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 شروع بازی", callback_data=f"is:{result_id}", style="success")]
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 بازیکنان و امتیازها", callback_data="admin:players:0", style="primary")],
            [InlineKeyboardButton(text="🔎 جستجوی کاربر با شناسه", callback_data="admin:search", style="primary")],
            [InlineKeyboardButton(text="↩️ بازگشت به منوی اصلی", callback_data="admin:home", style="danger")],
        ]
    )


def admin_players_keyboard(
    users: list[dict], page: int, total: int, page_size: int = 5
) -> InlineKeyboardMarkup:
    rows = []
    for user in users:
        username = user.get("username")
        if username:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"💬 پیوی {user['first_name'][:30]}",
                        url=f"https://t.me/{username}",
                        style="primary",
                    )
                ]
            )
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ قبلی", callback_data=f"admin:players:{page - 1}", style="primary"
            )
        )
    if (page + 1) * page_size < total:
        navigation.append(
            InlineKeyboardButton(
                text="بعدی ➡️", callback_data=f"admin:players:{page + 1}", style="primary"
            )
        )
    if navigation:
        rows.append(navigation)
    rows.append(
        [InlineKeyboardButton(text="↩️ بازگشت به پنل مدیریت", callback_data="admin:panel", style="danger")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_profile_keyboard(
    user_id: int, username: Optional[str] = None
) -> InlineKeyboardMarkup:
    rows = []
    if username:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💬 ورود به پیوی",
                    url=f"https://t.me/{username}",
                    style="primary",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="📜 تاریخچهٔ بازی‌ها",
                callback_data=f"admin:history:{user_id}:0",
                style="primary",
            )
        ]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def history_keyboard(user_id: int, page: int, total: int, page_size: int = 5) -> InlineKeyboardMarkup:
    buttons = []
    if page > 0:
        buttons.append(
            InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"admin:history:{user_id}:{page - 1}", style="primary")
        )
    if (page + 1) * page_size < total:
        buttons.append(
            InlineKeyboardButton(text="بعدی ➡️", callback_data=f"admin:history:{user_id}:{page + 1}", style="primary")
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [[
        InlineKeyboardButton(text="↩️ بازگشت به پروفایل", callback_data=f"admin:user:{user_id}", style="danger")
    ]])
