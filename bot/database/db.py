import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    draws INTEGER NOT NULL DEFAULT 0,
                    rating INTEGER NOT NULL DEFAULT 100
                );
                CREATE TABLE IF NOT EXISTS games (
                    game_id TEXT PRIMARY KEY,
                    game_type TEXT NOT NULL,
                    group_id INTEGER,
                    player_x_id INTEGER NOT NULL,
                    player_o_id INTEGER,
                    player_x_name TEXT NOT NULL,
                    player_o_name TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    played_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS game_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT NOT NULL REFERENCES games(game_id),
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    opponent_id INTEGER,
                    opponent_name TEXT NOT NULL,
                    result TEXT NOT NULL,
                    role TEXT NOT NULL,
                    score_before INTEGER NOT NULL,
                    score_after INTEGER NOT NULL,
                    delta INTEGER NOT NULL,
                    played_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_game_results_user
                    ON game_results(user_id, id DESC);
                CREATE TABLE IF NOT EXISTS inline_games (
                    game_id TEXT PRIMARY KEY,
                    inline_message_id TEXT NOT NULL UNIQUE,
                    board TEXT NOT NULL,
                    x_id INTEGER,
                    x_name TEXT,
                    o_id INTEGER,
                    o_name TEXT,
                    turn TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def save_inline_game(self, game: Any) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO inline_games(
                    game_id, inline_message_id, board, x_id, x_name, o_id, o_name, turn, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id) DO UPDATE SET
                    board = excluded.board,
                    x_id = excluded.x_id,
                    x_name = excluded.x_name,
                    o_id = excluded.o_id,
                    o_name = excluded.o_name,
                    turn = excluded.turn,
                    status = excluded.status
                """,
                (
                    game.game_id,
                    game.inline_message_id,
                    json.dumps(game.board),
                    game.x_id,
                    game.x_name,
                    game.o_id,
                    game.o_name,
                    game.turn,
                    game.status,
                ),
            )
            await db.commit()

    async def get_inline_game(self, game_id: str) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM inline_games WHERE game_id = ?", (game_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            game = dict(row)
            game["board"] = json.loads(game["board"])
            return game

    async def get_active_inline_game(
        self, inline_message_id: str
    ) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM inline_games
                WHERE inline_message_id = ? AND status != 'finished'
                """,
                (inline_message_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            game = dict(row)
            game["board"] = json.loads(game["board"])
            return game

    async def ensure_user(self, user_id: int, username: Optional[str], first_name: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users(user_id, username, first_name)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name
                """,
                (user_id, username, first_name),
            )
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_played_users(
        self, page: int, page_size: int = 5, exclude_user_id: Optional[int] = None
    ) -> tuple[list[dict[str, Any]], int]:
        offset = max(0, page) * page_size
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT COUNT(DISTINCT results.user_id)
                FROM game_results AS results
                JOIN users ON users.user_id = results.user_id
                WHERE (? IS NULL OR results.user_id != ?)
                """,
                (exclude_user_id, exclude_user_id),
            )
            total = int((await cursor.fetchone())[0])
            cursor = await db.execute(
                """
                SELECT users.*,
                    COUNT(results.id) AS games_played
                FROM users
                JOIN game_results AS results ON results.user_id = users.user_id
                GROUP BY users.user_id
                HAVING (? IS NULL OR users.user_id != ?)
                ORDER BY users.rating DESC, users.wins DESC, users.user_id ASC
                LIMIT ? OFFSET ?
                """,
                (exclude_user_id, exclude_user_id, page_size, offset),
            )
            return [dict(row) for row in await cursor.fetchall()], total

    async def record_game(
        self,
        *,
        game_id: str,
        game_type: str,
        group_id: Optional[int],
        x_id: int,
        o_id: Optional[int],
        x_name: str,
        o_name: str,
        outcome: str,
        human_role: Optional[str] = None,
    ) -> dict[int, int]:
        if outcome not in ("X", "O", "draw"):
            raise ValueError("Invalid game outcome.")
        if human_role not in (None, "X", "O"):
            raise ValueError("Invalid human role.")
        played_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        deltas: dict[int, int] = {}
        async with aiosqlite.connect(self.path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("BEGIN IMMEDIATE")
            score_rows: dict[int, int] = {}
            users_to_score = (
                (x_id if human_role == "X" else o_id,)
                if human_role is not None
                else (x_id, o_id)
            )
            for user_id in users_to_score:
                if user_id is None or user_id in score_rows:
                    continue
                cursor = await db.execute("SELECT rating FROM users WHERE user_id = ?", (user_id,))
                row = await cursor.fetchone()
                if row is None:
                    raise ValueError(f"User {user_id} must be registered before recording a game.")
                score_rows[user_id] = int(row[0])

            await db.execute(
                """
                INSERT INTO games(
                    game_id, game_type, group_id, player_x_id, player_o_id,
                    player_x_name, player_o_name, outcome, played_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (game_id, game_type, group_id, x_id, o_id, x_name, o_name, outcome, played_at),
            )
            if human_role is not None:
                user_id = x_id if human_role == "X" else o_id
                if user_id is None:
                    raise ValueError("Human player ID is missing.")
                opponent_name = o_name if human_role == "X" else x_name
                result = (
                    "draw" if outcome == "draw"
                    else "win" if outcome == human_role
                    else "loss"
                )
                players = [(user_id, None, opponent_name, human_role, result)]
            else:
                players = [
                    (x_id, o_id, o_name, "X", "win" if outcome == "X" else "loss" if outcome == "O" else "draw"),
                ]
                if o_id is not None:
                    players.append(
                        (o_id, x_id, x_name, "O", "win" if outcome == "O" else "loss" if outcome == "X" else "draw")
                    )
            for user_id, opponent_id, opponent_name, role, result in players:
                before = score_rows[user_id]
                requested_delta = 10 if result == "win" else -5 if result == "loss" else 2
                after = max(0, before + requested_delta)
                delta = after - before
                deltas[user_id] = delta
                await db.execute(
                    """
                    UPDATE users SET
                        wins = wins + ?, losses = losses + ?, draws = draws + ?, rating = ?
                    WHERE user_id = ?
                    """,
                    (int(result == "win"), int(result == "loss"), int(result == "draw"), after, user_id),
                )
                await db.execute(
                    """
                    INSERT INTO game_results(
                        game_id, user_id, opponent_id, opponent_name, result, role,
                        score_before, score_after, delta, played_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        game_id, user_id, opponent_id, opponent_name, result, role,
                        before, after, delta, played_at,
                    ),
                )
            await db.commit()
        return deltas

    async def get_history(self, user_id: int, page: int, page_size: int = 5) -> tuple[list[dict[str, Any]], int]:
        offset = max(0, page) * page_size
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT COUNT(*) FROM game_results WHERE user_id = ?", (user_id,)
            )
            total = int((await cursor.fetchone())[0])
            cursor = await db.execute(
                """
                SELECT * FROM game_results WHERE user_id = ?
                ORDER BY id DESC LIMIT ? OFFSET ?
                """,
                (user_id, page_size, offset),
            )
            return [dict(row) for row in await cursor.fetchall()], total
