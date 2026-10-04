import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_id: int
    database_path: str


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    admin_id = os.getenv("ADMIN_ID", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN در فایل .env تنظیم نشده است.")
    if not admin_id.isdigit():
        raise RuntimeError("ADMIN_ID باید یک شناسهٔ عددی تلگرام باشد.")
    project_root = Path(__file__).resolve().parent.parent
    database_path = Path(
        os.getenv("DATABASE_PATH", "tictactoe.sqlite3").strip()
        or "tictactoe.sqlite3"
    )
    if not database_path.is_absolute():
        database_path = project_root / database_path
    return Settings(
        bot_token=token,
        admin_id=int(admin_id),
        database_path=str(database_path.resolve()),
    )
