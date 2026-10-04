import random
from typing import Optional, Sequence

from bot.game.engine import winner


def _available(board: list[Optional[str]]) -> list[int]:
    return [index for index, cell in enumerate(board) if cell is None]


def _winning_move(board: list[Optional[str]], mark: str) -> Optional[int]:
    for index in _available(board):
        board[index] = mark
        won = winner(board) == mark
        board[index] = None
        if won:
            return index
    return None


def _minimax(
    board: list[Optional[str]],
    mark: str,
    ai_mark: str,
    depth: int,
    alpha: int,
    beta: int,
) -> tuple[int, Optional[int]]:
    result = winner(board)
    if result == ai_mark:
        return 10 - depth, None
    if result is not None:
        return depth - 10, None
    moves = _available(board)
    if not moves:
        return 0, None

    best_move: Optional[int] = None
    other_mark = "O" if mark == "X" else "X"
    if mark == ai_mark:
        best_score = -100
        for index in moves:
            board[index] = mark
            score, _ = _minimax(board, other_mark, ai_mark, depth + 1, alpha, beta)
            board[index] = None
            if score > best_score:
                best_score, best_move = score, index
            alpha = max(alpha, best_score)
            if beta <= alpha:
                break
    else:
        best_score = 100
        for index in moves:
            board[index] = mark
            score, _ = _minimax(board, other_mark, ai_mark, depth + 1, alpha, beta)
            board[index] = None
            if score < best_score:
                best_score, best_move = score, index
            beta = min(beta, best_score)
            if beta <= alpha:
                break
    return best_score, best_move


def _expert_move(
    board: list[Optional[str]], ai_mark: str, recent_moves: Sequence[int]
) -> int:
    scored = _score_moves(board, ai_mark)
    if not scored:
        raise ValueError("No AI move is available.")
    best_score = max(score for _, score in scored)
    best_moves = [move for move, score in scored if score == best_score]
    least_recently_used = min(recent_moves.count(move) for move in best_moves)
    candidates = [
        move for move in best_moves
        if recent_moves.count(move) == least_recently_used
    ]
    return random.choice(candidates)


def _score_moves(board: list[Optional[str]], ai_mark: str) -> list[tuple[int, int]]:
    scored: list[tuple[int, int]] = []
    opponent = "O" if ai_mark == "X" else "X"
    for move in _available(board):
        board[move] = ai_mark
        score, _ = _minimax(board, opponent, ai_mark, 1, -100, 100)
        board[move] = None
        scored.append((move, score))
    return scored


def _fork_moves(board: list[Optional[str]], mark: str) -> list[int]:
    forks = []
    for move in _available(board):
        board[move] = mark
        threats = sum(
            1
            for line in (
                (0, 1, 2), (3, 4, 5), (6, 7, 8),
                (0, 3, 6), (1, 4, 7), (2, 5, 8),
                (0, 4, 8), (2, 4, 6),
            )
            if sum(board[index] == mark for index in line) == 2
            and sum(board[index] is None for index in line) == 1
        )
        board[move] = None
        if threats > 1:
            forks.append(move)
    return forks


def _medium_move(board: list[Optional[str]], ai_mark: str) -> int:
    moves = _available(board)
    human_mark = "O" if ai_mark == "X" else "X"

    winning_move = _winning_move(board, ai_mark)
    if winning_move is not None:
        return winning_move
    blocking_move = _winning_move(board, human_mark)
    if blocking_move is not None:
        return blocking_move

    forks = _fork_moves(board, ai_mark)
    if forks:
        return random.choice(forks)

    opponent_forks = _fork_moves(board, human_mark)
    if opponent_forks:
        forcing_moves = []
        for move in moves:
            board[move] = ai_mark
            can_win_next = _winning_move(board, ai_mark) is not None
            board[move] = None
            if can_win_next:
                forcing_moves.append(move)
        if forcing_moves:
            return random.choice(forcing_moves)
        if 4 in opponent_forks and 4 in moves:
            return 4
        return random.choice(opponent_forks)

    if 4 in moves:
        return 4

    opposite_corners = [(0, 8), (2, 6)]
    for own_corner, opposite_corner in opposite_corners:
        if board[own_corner] == human_mark and opposite_corner in moves:
            return opposite_corner

    corners = [move for move in (0, 2, 6, 8) if move in moves]
    if corners:
        return random.choice(corners)
    return random.choice(moves)


def _easy_move(board: list[Optional[str]], ai_mark: str) -> int:
    moves = _available(board)
    human_mark = "O" if ai_mark == "X" else "X"

    winning_move = _winning_move(board, ai_mark)
    if winning_move is not None and random.random() < 0.85:
        return winning_move

    blocking_move = _winning_move(board, human_mark)
    if blocking_move is not None and random.random() < 0.7:
        return blocking_move

    if 4 in moves and random.random() < 0.5:
        return 4
    corners = [move for move in (0, 2, 6, 8) if move in moves]
    if corners and random.random() < 0.7:
        return random.choice(corners)
    return random.choice(moves)


def choose_move(
    board: list[Optional[str]],
    difficulty: str,
    ai_mark: str = "O",
    recent_moves: Sequence[int] = (),
) -> int:
    if ai_mark not in ("X", "O"):
        raise ValueError("AI mark must be X or O.")
    moves = _available(board)
    if not moves:
        raise ValueError("No AI move is available.")
    if difficulty == "expert":
        return _expert_move(board, ai_mark, recent_moves)

    if difficulty == "medium":
        return _medium_move(board, ai_mark)
    if difficulty == "easy":
        return _easy_move(board, ai_mark)
    raise ValueError("Unknown AI difficulty.")
