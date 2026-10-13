from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎮 شروع بازی", callback_data="menu:ai")],
        [InlineKeyboardButton(text="👤 پروفایل من", callback_data="menu:profile")],
        [InlineKeyboardButton(text="🏆 برترین بازیکنان", callback_data="menu:leaderboard")],
    ]
    if is_admin:
        rows.append(
            [InlineKeyboardButton(text="🛠 پنل مدیریت", callback_data="admin:panel")]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="💬 ارتباط با سازنده",
                url="https://t.me/moein_915",
            ),
        ]
    )
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def difficulty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🟢 آسان", callback_data="ai:easy")],
            [InlineKeyboardButton(text="🟡 متوسط", callback_data="ai:medium")],
            [InlineKeyboardButton(text="🔴 حرفه‌ای", callback_data="ai:expert")],
            [InlineKeyboardButton(text="⬅️", callback_data="menu:home")],
        ]
    )


def ai_symbol_keyboard(difficulty: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ بازی با X", callback_data=f"aisym:{difficulty}:X"),
                InlineKeyboardButton(text="⭕ بازی با O", callback_data=f"aisym:{difficulty}:O"),
            ],
            [InlineKeyboardButton(text="⬅️", callback_data="ai:levels")],
        ]
    )


def board_keyboard(
    board: list[Optional[str]],
    game_id: str,
    allow_back: bool = False,
) -> InlineKeyboardMarkup:
    symbols = {None: "⬜", "X": "❌", "O": "⭕"}
    rows = []
    for row in range(3):
        rows.append(
            [
                InlineKeyboardButton(
                    text=symbols[board[index]],
                    callback_data=f"b:{game_id}:{index}",
                    style={"X": "danger", "O": "primary"}.get(board[index]),
                )
                for index in range(row * 3, row * 3 + 3)
            ]
        )
    if allow_back:
        rows.append(
            [InlineKeyboardButton(text="⬅️", callback_data=f"aiback:{game_id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_finished_keyboard(
    board: list[Optional[str]],
    game_id: str,
    is_admin: bool = False,
) -> InlineKeyboardMarkup:
    keyboard = board_keyboard(board, game_id).inline_keyboard
    keyboard.append(
        [
            InlineKeyboardButton(
                text="🔄 دوباره بازی کردن",
                callback_data=f"aireplay:{game_id}",
            ),
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"aimenu:{game_id}:{int(is_admin)}",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️", callback_data="menu:home")]
        ]
    )


def join_keyboard(game_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 شروع بازی / ورود", callback_data=f"gj:{game_id}")]
        ]
    )


def inline_join_keyboard(game_id: str, owner_name: str = "") -> InlineKeyboardMarkup:
    prefix = f"ii:{game_id}:"
    safe_owner_name = _truncate_utf8(owner_name, 64 - len(prefix.encode("utf-8")))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 ورود به بازی",
                    callback_data=f"{prefix}{safe_owner_name}",
                    style="primary",
                )
            ]
        ]
    )


def _truncate_utf8(value: str, max_bytes: int) -> str:
    return value.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 بازیکنان و امتیازها", callback_data="admin:players:0")],
            [InlineKeyboardButton(text="⬅️", callback_data="admin:home")],
        ]
    )


def admin_players_keyboard(
    users: list[dict],
    page: int,
    total: int,
    page_size: int = 5,
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
                    )
                ]
            )
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ قبلی", callback_data=f"admin:players:{page - 1}"
            )
        )
    if (page + 1) * page_size < total:
        navigation.append(
            InlineKeyboardButton(
                text="بعدی ➡️", callback_data=f"admin:players:{page + 1}"
            )
        )
    if navigation:
        rows.append(navigation)
    rows.append(
        [InlineKeyboardButton(text="⬅️", callback_data="admin:panel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def leaderboard_keyboard(
    page: int, total: int, page_size: int = 5
) -> InlineKeyboardMarkup:
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ قبلی",
                callback_data=f"menu:leaderboard:{page - 1}",
            )
        )
    if (page + 1) * page_size < total:
        navigation.append(
            InlineKeyboardButton(
                text="بعدی ➡️",
                callback_data=f"menu:leaderboard:{page + 1}",
            )
        )
    rows = [navigation] if navigation else []
    rows.append(
        [InlineKeyboardButton(text="⬅️", callback_data="menu:home")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_profile_keyboard(
    user_id: int, username: Optional[str] = None, show_back: bool = True
) -> InlineKeyboardMarkup:
    rows = []
    if username:
        rows.append(
            [
                InlineKeyboardButton(
                    text="💬 ورود به پیوی",
                    url=f"https://t.me/{username}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="📜 تاریخچهٔ بازی‌ها",
                callback_data=f"admin:history:{user_id}:0",
            )
        ]
    )
    if show_back:
        rows.append([InlineKeyboardButton(text="⬅️", callback_data="admin:panel")])
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def history_keyboard(
    user_id: int,
    page: int,
    total: int,
    page_size: int = 5,
) -> InlineKeyboardMarkup:
    buttons = []
    if page > 0:
        buttons.append(
            InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"admin:history:{user_id}:{page - 1}")
        )
    if (page + 1) * page_size < total:
        buttons.append(
            InlineKeyboardButton(text="بعدی ➡️", callback_data=f"admin:history:{user_id}:{page + 1}")
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons] if buttons else [[
        InlineKeyboardButton(
            text="⬅️",
            callback_data=f"admin:user:{user_id}",
        )
    ]])
