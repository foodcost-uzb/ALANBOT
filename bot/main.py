import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from .config import BOT_TOKEN
from .database import close_db, init_db
from .handlers import get_all_routers
from .scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Check your .env file.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    for router in get_all_routers():
        dp.include_router(router)

    # Init database
    await init_db()
    logger.info("Database initialized")

    # Start scheduler
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started")

    # Start polling
    logger.info("Bot is starting...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
