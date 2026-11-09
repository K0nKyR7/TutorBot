import asyncio
import logging
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

async def main():
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN не установлен! Пожалуйста, укажите токен в файле .env")
        print("\n[ОШИБКА]: Переменная BOT_TOKEN не заполнена в файле .env!\nСоздайте бота в @BotFather и вставьте токен в tutor_crm_bot/.env\n")
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

    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
