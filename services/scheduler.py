import logging
from datetime import datetime, date, time
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.crm_service import TutorService, LessonService

logger = logging.getLogger(__name__)

async def send_daily_digests(bot: Bot):
    """
    Каждое утро рассылает репетиторам расписание на текущий день.
    """
    try:
        tutors = await TutorService.get_all_tutors_with_digest()
        today = date.today()
        start_dt = datetime.combine(today, time.min)
        end_dt = datetime.combine(today, time.max)

        for tutor in tutors:
            lessons = await LessonService.get_lessons_for_date_range(tutor.telegram_id, start_dt, end_dt)
            if not lessons:
                continue

            text = f"☀️ <b>Доброе утро! План занятий на сегодня ({today.strftime('%d.%m.%Y')}):</b>\n\n"
            for idx, l in enumerate(lessons, 1):
                dt_str = l.scheduled_at.strftime("%H:%M")
                st_name = l.student.name if l.student else "Ученик"
                topic_str = f" | {l.topic}" if l.topic else ""
                text += f"{idx}. ⏰ <b>{dt_str}</b> — {st_name} ({l.duration_minutes} мин.){topic_str}\n"

            text += "\n<i>Удачного и продуктивного учебного дня! 🚀</i>"
            try:
                await bot.send_message(chat_id=tutor.telegram_id, text=text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Не удалось отправить утренний дайджест репетитору {tutor.telegram_id}: {e}")
    except Exception as ex:
        logger.error(f"Ошибка в задаче send_daily_digests: {ex}")

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Запуск каждое утро в 08:00
    scheduler.add_job(send_daily_digests, "cron", hour=8, minute=0, args=[bot])
    return scheduler
