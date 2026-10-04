import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent

from bot.config import load_settings
from bot.database.db import Database
from bot.handlers import admin, games, start


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = load_settings()
    db = Database(settings.database_path)
    await db.initialize()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher["db"] = db
    dispatcher["admin_id"] = settings.admin_id
    dispatcher.include_routers(start.router, admin.router, games.router)

    @dispatcher.errors()
    async def handle_error(event: ErrorEvent) -> bool:
        logging.getLogger(__name__).error(
            "Unhandled update error",
            exc_info=(
                type(event.exception),
                event.exception,
                event.exception.__traceback__,
            ),
        )
        try:
            if event.update.callback_query:
                await event.update.callback_query.answer(
                    "خطایی رخ داد. لطفاً دوباره تلاش کنید.", show_alert=True
                )
            elif event.update.message:
                await event.update.message.answer("خطایی رخ داد. لطفاً دوباره تلاش کنید.")
        except TelegramAPIError:
            logging.getLogger(__name__).debug(
                "Unable to notify the user about the failed update", exc_info=True
            )
        return True

    me = await bot.get_me()
    games.set_bot_username(me.username or "")
    logging.info("Bot started as @%s", me.username)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
