import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database.db import init_db
from handlers.base_handlers import base_router
from handlers.student_handlers import students_router
from handlers.schedule_handlers import schedule_router
from services.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

async def start_dummy_web_server():
    """
    Фейковый веб-сервер для бесплатного тарифа Render (Web Service).
    Render требует, чтобы сервис слушал порт из переменной PORT.
    """
    port = int(os.getenv("PORT", 8080))
    app = web.Application()

    async def handle_ping(request):
        return web.Response(text="TutorCRM Bot is running!")

    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Фоновый веб-сервер для Render запущен на порту {port}")

async def main():
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN не установлен! Пожалуйста, укажите токен в файле .env или переменных окружения.")
        return

    # Инициализация базы данных
    await init_db()
    logger.info("База данных успешно инициализирована.")

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Настройка планировщика утренних дайджестов
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Планировщик фоновых задач запущен (утренний дайджест в 08:00).")

    # Подключаем роутеры
    dp.include_router(base_router)
    dp.include_router(students_router)
    dp.include_router(schedule_router)

    # Если бот запущен на хостинге с портом (Render / Heroku)
    if os.getenv("PORT"):
        await start_dummy_web_server()

    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
