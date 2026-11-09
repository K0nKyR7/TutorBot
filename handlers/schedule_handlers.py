from datetime import datetime, date, time, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.crm_service import LessonService
from keyboards.crm_keyboards import get_schedule_menu, get_lesson_action_keyboard, get_cancel_keyboard

schedule_router = Router()

class LessonHWFSM(StatesGroup):
    lesson_id = State()
    topic = State()
    homework = State()

class RescheduleFSM(StatesGroup):
    lesson_id = State()
    new_dt_str = State()

@schedule_router.callback_query(F.data == "menu_schedule")
async def cb_schedule_menu(callback: CallbackQuery, state: FSMContext):
    if state:
        await state.clear()
    await callback.message.edit_text(
        "📅 <b>Расписание занятий</b>\n\nВыберите период для просмотра:",
        parse_mode="HTML",
        reply_markup=get_schedule_menu()
    )
    await callback.answer()

@schedule_router.callback_query(F.data == "sched_generate")
async def cb_generate_lessons(callback: CallbackQuery):
    count = await LessonService.generate_lessons_from_slots(callback.from_user.id, days_ahead=14)
    await callback.answer(f"Сгенерировано уроков: {count}", show_alert=True)
    await cb_schedule_menu(callback, None)

@schedule_router.callback_query(F.data == "sched_today")
async def cb_sched_today(callback: CallbackQuery):
    today = date.today()
    start_dt = datetime.combine(today, time.min)
    end_dt = datetime.combine(today, time.max)
    
    lessons = await LessonService.get_lessons_for_date_range(callback.from_user.id, start_dt, end_dt)
    await render_lessons_list(callback, lessons, f"Сегодня ({today.strftime('%d.%m.%Y')})")

@schedule_router.callback_query(F.data == "sched_tomorrow")
async def cb_sched_tomorrow(callback: CallbackQuery):
    tomorrow = date.today() + timedelta(days=1)
    start_dt = datetime.combine(tomorrow, time.min)
    end_dt = datetime.combine(tomorrow, time.max)
    
    lessons = await LessonService.get_lessons_for_date_range(callback.from_user.id, start_dt, end_dt)
    await render_lessons_list(callback, lessons, f"Завтра ({tomorrow.strftime('%d.%m.%Y')})")

@schedule_router.callback_query(F.data == "sched_week")
async def cb_sched_week(callback: CallbackQuery):
    today = date.today()
    start_dt = datetime.combine(today, time.min)
    end_dt = datetime.combine(today + timedelta(days=7), time.max)
    
    lessons = await LessonService.get_lessons_for_date_range(callback.from_user.id, start_dt, end_dt)
    await render_lessons_list(callback, lessons, "Ближайшие 7 дней")

async def render_lessons_list(callback: CallbackQuery, lessons: list, period_title: str):
    if not lessons:
        kb = [[InlineKeyboardButton(text="🔙 К расписанию", callback_data="menu_schedule")]]
        await callback.message.edit_text(
            f"📅 <b>Уроки на {period_title}:</b>\n\n<i>Занятий не запланировано.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
        await callback.answer()
        return

    text = f"📅 <b>Уроки на {period_title}:</b>\n\n"
    kb = []
    
    status_emoji = {
        "scheduled": "⏳",
        "completed": "✅",
        "cancelled_by_student": "❌",
        "cancelled_by_tutor": "🚫"
    }

    for l in lessons:
        dt_str = l.scheduled_at.strftime("%d.%m %H:%M")
        icon = status_emoji.get(l.status, "⏳")
        student_name = l.student.name if l.student else "Ученик"
        text += f"{icon} <b>{dt_str}</b> — {student_name} ({l.duration_minutes} мин.)\n"
        
        kb.append([
            InlineKeyboardButton(
                text=f"{icon} {dt_str} {student_name}",
                callback_data=f"lesson_view_{l.id}"
            )
        ])

    kb.append([InlineKeyboardButton(text="🔙 К расписанию", callback_data="menu_schedule")])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@schedule_router.callback_query(F.data.startswith("lesson_view_"))
async def cb_lesson_view(callback: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    lesson_id = int(callback.data.split("_")[2])
    lesson = await LessonService.get_lesson_by_id(lesson_id, callback.from_user.id)
    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    status_ru = {
        "scheduled": "Запланирован ⏳",
        "completed": "Проведен ✅",
        "cancelled_by_student": "Отменен учеником ❌",
        "cancelled_by_tutor": "Отменен репетитором 🚫"
    }

    st_name = lesson.student.name if lesson.student else "Не указан"
    topic_str = lesson.topic if lesson.topic else "<i>Не заполнена</i>"
    hw_str = lesson.homework if lesson.homework else "<i>Не задано</i>"

    text = (
        f"📖 <b>Информация об уроке</b>\n\n"
        f"👤 <b>Ученик:</b> {st_name}\n"
        f"⏰ <b>Дата и время:</b> {lesson.scheduled_at.strftime('%d.%m.%Y в %H:%M')}\n"
        f"⏳ <b>Длительность:</b> {lesson.duration_minutes} мин.\n"
        f"💵 <b>Стоимость:</b> {lesson.price:,.0f} ₽\n"
        f"📌 <b>Статус:</b> {status_ru.get(lesson.status, lesson.status)}\n\n"
        f"🎯 <b>Тема:</b> {topic_str}\n"
        f"📚 <b>Домашнее задание:</b> {hw_str}\n\n"
        f"Действия с уроком:"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_lesson_action_keyboard(lesson)
    )
    await callback.answer()

@schedule_router.callback_query(F.data.startswith("lesson_status_"))
async def cb_lesson_status(callback: CallbackQuery):
    parts = callback.data.split("_")
    lesson_id = int(parts[2])
    new_status = "_".join(parts[3:])

    lesson = await LessonService.mark_lesson_status(lesson_id, callback.from_user.id, new_status)
    if lesson:
        if new_status == "completed":
            await callback.answer("Урок отмечен как проведенный! Баланс списан.", show_alert=True)
        else:
            await callback.answer("Статус урока обновлен.", show_alert=False)
        await cb_lesson_view(callback)

# --- Добавление темы и домашнего задания ---

@schedule_router.callback_query(F.data.startswith("lesson_hw_"))
async def cb_lesson_hw_start(callback: CallbackQuery, state: FSMContext):
    lesson_id = int(callback.data.split("_")[2])
    await state.set_state(LessonHWFSM.topic)
    await state.update_data(lesson_id=lesson_id)
    
    await callback.message.edit_text(
        "📝 <b>Тема урока и домашнее задание (Шаг 1 из 2)</b>\n\n"
        "Введите <b>тему урока</b> (например: <i>Квадратные уравнения / Past Simple</i>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(f"lesson_view_{lesson_id}")
    )
    await callback.answer()

@schedule_router.message(LessonHWFSM.topic)
async def process_lesson_topic(message: Message, state: FSMContext):
    topic = message.text.strip()
    await state.update_data(topic=topic)
    await state.set_state(LessonHWFSM.homework)
    
    data = await state.get_data()
    lesson_id = data["lesson_id"]

    await message.answer(
        "📚 <b>Шаг 2 из 2</b>\n\n"
        "Введите <b>домашнее задание</b> к уроку (или отправьте '-' если без ДЗ):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(f"lesson_view_{lesson_id}")
    )

@schedule_router.message(LessonHWFSM.homework)
async def process_lesson_hw(message: Message, state: FSMContext):
    hw = message.text.strip()
    if hw == "-":
        hw = ""
    data = await state.get_data()
    lesson_id = data["lesson_id"]
    topic = data["topic"]

    await LessonService.update_lesson_materials(lesson_id, message.from_user.id, topic=topic, homework=hw)
    await state.clear()

    lesson = await LessonService.get_lesson_by_id(lesson_id, message.from_user.id)
    await message.answer(
        "✅ Тема и домашнее задание успешно сохранены!",
        reply_markup=get_lesson_action_keyboard(lesson)
    )

# --- Перенос урока ---

@schedule_router.callback_query(F.data.startswith("lesson_reschedule_"))
async def cb_reschedule_start(callback: CallbackQuery, state: FSMContext):
    lesson_id = int(callback.data.split("_")[2])
    await state.set_state(RescheduleFSM.new_dt_str)
    await state.update_data(lesson_id=lesson_id)

    await callback.message.edit_text(
        "🕒 <b>Перенос занятия</b>\n\n"
        "Введите новую дату и время в формате <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>\n"
        "Например: <i>18.11.2026 15:00</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(f"lesson_view_{lesson_id}")
    )
    await callback.answer()

@schedule_router.message(RescheduleFSM.new_dt_str)
async def process_reschedule(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        new_dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("Неверный формат даты! Введите как: <b>18.11.2026 15:00</b>", parse_mode="HTML")
        return

    data = await state.get_data()
    lesson_id = data["lesson_id"]
    lesson = await LessonService.reschedule_lesson(lesson_id, message.from_user.id, new_dt)
    await state.clear()

    if lesson:
        await message.answer(
            f"✅ Урок успешно перенесен на <b>{new_dt.strftime('%d.%m.%Y в %H:%M')}</b>!",
            parse_mode="HTML",
            reply_markup=get_lesson_action_keyboard(lesson)
        )
