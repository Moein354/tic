import asyncio
from dataclasses import dataclass, field
from typing import Optional


WINNING_LINES = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


def winner(board: list[Optional[str]]) -> Optional[str]:
    for a, b, c in WINNING_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def is_draw(board: list[Optional[str]]) -> bool:
    return winner(board) is None and all(board)


@dataclass
class GroupGame:
    game_id: str
    chat_id: Optional[int]
    message_id: Optional[int]
    inline_message_id: Optional[str] = None
    board: list[Optional[str]] = field(default_factory=lambda: [None] * 9)
    x_id: Optional[int] = None
    x_name: Optional[str] = None
    o_id: Optional[int] = None
    o_name: Optional[str] = None
    turn: str = "X"
    status: str = "waiting"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


@dataclass
class AiGame:
    game_id: str
    user_id: int
    user_name: str
    difficulty: str
    human_mark: str = "X"
    board: list[Optional[str]] = field(default_factory=lambda: [None] * 9)
    status: str = "playing"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def ai_mark(self) -> str:
        return "O" if self.human_mark == "X" else "X"
