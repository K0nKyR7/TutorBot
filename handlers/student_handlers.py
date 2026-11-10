import re
from datetime import time, datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.crm_service import StudentService, FinanceService, LessonService
from keyboards.crm_keyboards import (
    get_students_menu,
    get_student_card_keyboard,
    get_confirm_delete_keyboard,
    get_days_keyboard,
    get_cancel_keyboard,
    DAYS_FULL
)

students_router = Router()

class AddStudentFSM(StatesGroup):
    name = State()
    subject = State()
    contact = State()
    billing_type = State()
    price = State()
    notes = State()

class PaymentFSM(StatesGroup):
    student_id = State()
    amount = State()
    lessons_count = State()

class AddSlotFSM(StatesGroup):
    student_id = State()
    day_of_week = State()
    time_str = State()
    subject = State()
    price = State()

class EditNotesFSM(StatesGroup):
    student_id = State()
    notes = State()

class AddSingleLessonFSM(StatesGroup):
    student_id = State()
    datetime_str = State()
    duration = State()
    subject = State()
    price = State()

# --- Просмотр учеников ---

@students_router.callback_query(F.data == "menu_students")
async def cb_students_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    students = await StudentService.get_tutor_students(callback.from_user.id)
    if not students:
        text = "👥 <b>Список учеников пуст</b>\n\nНажмите кнопку ниже, чтобы добавить вашего первого ученика:"
    else:
        text = "👥 <b>Ваши ученики:</b>\nНажмите на имя ученика, чтобы открыть его карточку:"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_students_menu(students)
    )
    await callback.answer()

@students_router.callback_query(F.data.startswith("student_view_"))
async def cb_view_student(callback: CallbackQuery, state: FSMContext):
    if state:
        await state.clear()
    student_id = int(callback.data.split("_")[2])
    student = await StudentService.get_student_by_id(student_id, callback.from_user.id)
    
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return

    status_str = "Активен ✅" if student.is_active else "В архиве 📦"
    
    billing_names = {
        "per_lesson": "Поурочная оплата",
        "package": "Пакет (абонемент)",
        "postpaid_weekly": "Постоплата (в конце недели)"
    }
    billing_type_str = billing_names.get(student.billing_type, student.billing_type)
    
    slots_text = ""
    if student.recurring_slots:
        slots_list = []
        for s in student.recurring_slots:
            slot_subj = f" [{s.subject}]" if s.subject else ""
            slot_pr = f" ({s.price:,.0f} ₽)" if s.price is not None else ""
            slots_list.append(f"• {DAYS_FULL[s.day_of_week]} в {s.start_time.strftime('%H:%M')}{slot_subj}{slot_pr} ({s.duration_minutes} мин.)")
        slots_text = "\n".join(slots_list)
    else:
        slots_text = "<i>Регулярное расписание не настроено</i>"

    if student.billing_type == "package":
        balance_info = f"Оплачено уроков: <b>{student.prepaid_lessons_left} шт.</b>"
    elif student.billing_type == "postpaid_weekly":
        if student.balance_rub < 0:
            balance_info = f"К оплате за неделю: <b>{abs(student.balance_rub):,.0f} ₽</b>"
        else:
            balance_info = f"Баланс: <b>{student.balance_rub:+.0f} ₽</b>"
    else:
        balance_info = f"Баланс: <b>{student.balance_rub:+.0f} ₽</b>"

    notes_text = student.notes if student.notes else "<i>Нет заметок</i>"

    plan = StudentService.calculate_student_plan_income(student)

    text = (
        f"👤 <b>Карточка ученика: {student.name}</b>\n\n"
        f"📚 <b>Предмет(ы):</b> {student.subject or 'Не указан'}\n"
        f"📱 <b>Контакт:</b> {student.contact or 'Не указан'}\n"
        f"📊 <b>Статус:</b> {status_str}\n"
        f"💵 <b>Тариф:</b> {billing_type_str} (базовая ставка: {student.lesson_price:,.0f} ₽/ур.)\n"
        f"💰 <b>{balance_info}</b>\n"
        f"📈 <b>Доход от ученика:</b> ~{plan['weekly']:,.0f} ₽/нед. (<b>~{plan['monthly']:,.0f} ₽/мес.</b>)\n"
        f"📝 <b>Заметки / Цель:</b> {notes_text}\n\n"
        f"🗓 <b>Регулярное расписание:</b>\n{slots_text}\n"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_student_card_keyboard(student)
    )
    await callback.answer()

@students_router.callback_query(F.data.startswith("student_toggle_"))
async def cb_toggle_student(callback: CallbackQuery):
    student_id = int(callback.data.split("_")[2])
    student = await StudentService.toggle_active(student_id, callback.from_user.id)
    if student:
        msg = "Ученик перенесен в архив" if not student.is_active else "Ученик восстановлен из архива"
        await callback.answer(msg, show_alert=True)
        await cb_view_student(callback, None)

@students_router.callback_query(F.data.startswith("student_del_ask_"))
async def cb_delete_student_ask(callback: CallbackQuery):
    student_id = int(callback.data.split("_")[3])
    student = await StudentService.get_student_by_id(student_id, callback.from_user.id)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return

    text = (
        f"⚠️ <b>Внимание! Вы уверены, что хотите удалить ученика {student.name}?</b>\n\n"
        f"Это действие <b>безвозвратно удалит</b> ученика, все его расписание, историю уроков и платежи из базы данных.\n"
        f"Ученик больше не будет появляться ни в одном отчете."
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_confirm_delete_keyboard(student_id)
    )
    await callback.answer()

@students_router.callback_query(F.data.startswith("student_del_confirm_"))
async def cb_delete_student_confirm(callback: CallbackQuery):
    student_id = int(callback.data.split("_")[3])
    success = await StudentService.delete_student_permanently(student_id, callback.from_user.id)
    if success:
        await callback.answer("Ученик безвозвратно удален из базы данных", show_alert=True)
        # Возвращаем в список учеников
        await cb_students_list(callback, None)
    else:
        await callback.answer("Ошибка при удалении ученика", show_alert=True)

# --- Редактирование заметок ---

@students_router.callback_query(F.data.startswith("student_notes_"))
async def cb_edit_notes_start(callback: CallbackQuery, state: FSMContext):
    student_id = int(callback.data.split("_")[2])
    student = await StudentService.get_student_by_id(student_id, callback.from_user.id)
    if not student:
        return
    await state.set_state(EditNotesFSM.notes)
    await state.update_data(student_id=student_id)
    await callback.message.edit_text(
        f"📝 <b>Заметки по ученику {student.name}</b>\n\n"
        f"Текущая заметка: {student.notes or '<i>пусто</i>'}\n\n"
        f"Отправьте новый текст заметки (цель обучения, ссылки на материалы, слабые темы и т.д.):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(f"student_view_{student_id}")
    )
    await callback.answer()

@students_router.message(EditNotesFSM.notes)
async def process_notes_save(message: Message, state: FSMContext):
    data = await state.get_data()
    student_id = data["student_id"]
    await StudentService.update_student_notes(student_id, message.from_user.id, message.text.strip())
    await state.clear()
    
    student = await StudentService.get_student_by_id(student_id, message.from_user.id)
    await message.answer(
        f"✅ Заметка для <b>{student.name}</b> обновлена!",
        parse_mode="HTML",
        reply_markup=get_student_card_keyboard(student)
    )

# --- Добавление разового урока ---

@students_router.callback_query(F.data.startswith("lesson_add_single_"))
async def cb_add_single_start(callback: CallbackQuery, state: FSMContext):
    student_id = int(callback.data.split("_")[3])
    student = await StudentService.get_student_by_id(student_id, callback.from_user.id)
    if not student:
        return
    await state.set_state(AddSingleLessonFSM.datetime_str)
    await state.update_data(student_id=student_id, default_subject=student.subject, default_price=student.lesson_price)
    
    await callback.message.edit_text(
        f"➕ <b>Назначение разового урока для {student.name} (Шаг 1 из 4)</b>\n\n"
        f"Введите дату и время урока в формате <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>\n"
        f"Например: <i>15.11.2026 17:30</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(f"student_view_{student_id}")
    )
    await callback.answer()

@students_router.message(AddSingleLessonFSM.datetime_str)
async def process_single_datetime(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("Неверный формат! Введите дату и время как: <b>15.11.2026 17:30</b>", parse_mode="HTML")
        return

    await state.update_data(scheduled_at=dt.isoformat())
    await state.set_state(AddSingleLessonFSM.duration)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="45 мин", callback_data="single_dur_45"),
            InlineKeyboardButton(text="60 мин", callback_data="single_dur_60"),
            InlineKeyboardButton(text="90 мин", callback_data="single_dur_90")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_schedule")]
    ])
    await message.answer("Шаг 2 из 4: Выберите длительность урока:", reply_markup=kb)

@students_router.callback_query(AddSingleLessonFSM.duration, F.data.startswith("single_dur_"))
async def process_single_duration(callback: CallbackQuery, state: FSMContext):
    dur = int(callback.data.split("_")[2])
    await state.update_data(duration=dur)
    await state.set_state(AddSingleLessonFSM.subject)
    
    data = await state.get_data()
    def_sub = data.get("default_subject", "")
    
    await callback.message.edit_text(
        f"📚 <b>Шаг 3 из 4: Предмет урока</b>\n\n"
        f"Введите предмет для этого занятия (например: <i>Математика</i> или <i>Физика</i>).\n"
        f"Или отправьте <b>-</b>, чтобы оставить по умолчанию: <i>{def_sub}</i>",
        parse_mode="HTML"
    )
    await callback.answer()

@students_router.message(AddSingleLessonFSM.subject)
async def process_single_subject(message: Message, state: FSMContext):
    sub = message.text.strip()
    data = await state.get_data()
    if sub == "-":
        sub = data.get("default_subject", "")
    await state.update_data(subject=sub)
    await state.set_state(AddSingleLessonFSM.price)

    def_pr = data.get("default_price", 0.0)
    await message.answer(
        f"💰 <b>Шаг 4 из 4: Стоимость урока</b>\n\n"
        f"Введите стоимость в рублях (например: <i>1500</i> или <i>2000</i>).\n"
        f"Или отправьте <b>-</b>, чтобы использовать базовую ставку: <i>{def_pr:,.0f} ₽</i>",
        parse_mode="HTML"
    )

@students_router.message(AddSingleLessonFSM.price)
async def process_single_price(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    
    if text == "-":
        price = data.get("default_price", 0.0)
    else:
        try:
            price = float(text.replace(" ", "").replace(",", "."))
        except ValueError:
            await message.answer("Пожалуйста, введите число (стоимость в рублях) или '-' для базовой ставки:")
            return

    student_id = data["student_id"]
    scheduled_at = datetime.fromisoformat(data["scheduled_at"])
    dur = data["duration"]
    subj = data["subject"]

    lesson = await LessonService.create_single_lesson(
        tutor_id=message.from_user.id,
        student_id=student_id,
        scheduled_at=scheduled_at,
        duration=dur,
        subject=subj,
        price=price
    )
    await state.clear()

    student = await StudentService.get_student_by_id(student_id, message.from_user.id)
    await message.answer(
        f"✅ <b>Разовый урок назначен!</b>\n\n"
        f"👤 Ученик: <b>{student.name}</b>\n"
        f"📚 Предмет: <b>{subj}</b>\n"
        f"⏰ Дата и время: <b>{scheduled_at.strftime('%d.%m.%Y в %H:%M')}</b> ({dur} мин.)\n"
        f"💵 Стоимость: <b>{lesson.price:,.0f} ₽</b>",
        parse_mode="HTML",
        reply_markup=get_student_card_keyboard(student)
    )

# --- Добавление ученика (FSM) ---

@students_router.callback_query(F.data == "student_add")
async def cb_add_student_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddStudentFSM.name)
    await callback.message.edit_text(
        "📝 <b>Добавление ученика (Шаг 1 из 5)</b>\n\nВведите <b>Имя и Фамилию</b> ученика (например: <i>Алексей Иванов</i>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard("menu_students")
    )
    await callback.answer()

@students_router.message(AddStudentFSM.name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, введите корректное имя:")
        return
    await state.update_data(name=name)
    await state.set_state(AddStudentFSM.subject)
    await message.answer(
        f"📚 <b>Шаг 2 из 5</b>\n\nКакие предметы изучаете с <b>{name}</b>? (можно перечислить через запятую, например: <i>Математика, Физика</i>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard("menu_students")
    )

@students_router.message(AddStudentFSM.subject)
async def process_subject(message: Message, state: FSMContext):
    subject = message.text.strip()
    await state.update_data(subject=subject)
    await state.set_state(AddStudentFSM.contact)
    await message.answer(
        "📱 <b>Шаг 3 из 5</b>\n\nУкажите контакт ученика или родителя (Telegram @username, телефон или ссылку):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard("menu_students")
    )

@students_router.message(AddStudentFSM.contact)
async def process_contact(message: Message, state: FSMContext):
    contact = message.text.strip()
    await state.update_data(contact=contact)
    await state.set_state(AddStudentFSM.billing_type)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Поурочная оплата", callback_data="billing_per_lesson")],
        [InlineKeyboardButton(text="📦 Абонемент / Пакет уроков", callback_data="billing_package")],
        [InlineKeyboardButton(text="🗓 Постоплата (в конце недели)", callback_data="billing_postpaid_weekly")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_students")]
    ])
    await message.answer(
        "💵 <b>Шаг 4 из 5</b>\n\nВыберите схему оплаты для этого ученика:",
        parse_mode="HTML",
        reply_markup=kb
    )

@students_router.callback_query(AddStudentFSM.billing_type, F.data.startswith("billing_"))
async def process_billing(callback: CallbackQuery, state: FSMContext):
    if callback.data == "billing_package":
        b_type = "package"
    elif callback.data == "billing_postpaid_weekly":
        b_type = "postpaid_weekly"
    else:
        b_type = "per_lesson"

    await state.update_data(billing_type=b_type)
    await state.set_state(AddStudentFSM.price)
    
    await callback.message.edit_text(
        "💰 <b>Шаг 5 из 5</b>\n\nВведите <b>базовую стоимость урока</b> в рублях (например: <i>1500</i>).\n<i>(В расписании для каждого отдельного предмета вы сможете задать свою цену)</i>:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard("menu_students")
    )
    await callback.answer()

@students_router.message(AddStudentFSM.price)
async def process_price(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "").replace(",", ".")
    try:
        price = float(text)
        if price < 0:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите положительное число (например: 1500):")
        return

    data = await state.get_data()
    student = await StudentService.create_student(
        tutor_id=message.from_user.id,
        name=data["name"],
        contact=data["contact"],
        subject=data["subject"],
        billing_type=data["billing_type"],
        lesson_price=price,
        initial_prepaid=0,
        initial_balance=0.0
    )
    await state.clear()

    await message.answer(
        f"🎉 <b>Ученик {student.name} успешно добавлен!</b>\n\n"
        f"Теперь вы можете настроить для него регулярное расписание занятий с отдельными предметами и ценами.",
        parse_mode="HTML",
        reply_markup=get_student_card_keyboard(student)
    )

# --- Настройка регулярных слотов расписания ---

@students_router.callback_query(F.data.startswith("student_slots_"))
async def cb_student_slots(callback: CallbackQuery, state: FSMContext):
    if state:
        await state.clear()
    student_id = int(callback.data.split("_")[2])
    student = await StudentService.get_student_by_id(student_id, callback.from_user.id)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return

    kb = []
    text = f"🗓 <b>Регулярное расписание для {student.name}</b>\n\n"
    if student.recurring_slots:
        text += "Текущие дни занятий:\n"
        for s in student.recurring_slots:
            slot_subj = f" [{s.subject}]" if s.subject else ""
            slot_pr = f" ({s.price:,.0f} ₽)" if s.price is not None else ""
            text += f"• <b>{DAYS_FULL[s.day_of_week]}</b> в <b>{s.start_time.strftime('%H:%M')}</b>{slot_subj}{slot_pr}\n"
            kb.append([InlineKeyboardButton(text=f"🗑 Удалить {DAYS_FULL[s.day_of_week]} {s.start_time.strftime('%H:%M')}{slot_subj}", callback_data=f"del_slot_{s.id}_{student.id}")])
    else:
        text += "<i>Пока нет добавленных дней занятий.</i>\n"

    kb.append([InlineKeyboardButton(text="➕ Добавить день и время", callback_data=f"add_slot_{student.id}")])
    kb.append([InlineKeyboardButton(text="🔙 К карточке ученика", callback_data=f"student_view_{student.id}")])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@students_router.callback_query(F.data.startswith("del_slot_"))
async def cb_del_slot(callback: CallbackQuery):
    parts = callback.data.split("_")
    slot_id = int(parts[2])
    student_id = int(parts[3])
    await StudentService.delete_recurring_slot(slot_id)
    await callback.answer("Слот удален", show_alert=False)
    callback.data = f"student_slots_{student_id}"
    await cb_student_slots(callback, None)

@students_router.callback_query(F.data.startswith("add_slot_") & ~F.data.startswith("add_slot_day_"))
async def cb_add_slot_start(callback: CallbackQuery, state: FSMContext):
    student_id = int(callback.data.split("_")[2])
    student = await StudentService.get_student_by_id(student_id, callback.from_user.id)
    await state.set_state(AddSlotFSM.day_of_week)
    await state.update_data(student_id=student_id, default_subject=student.subject, default_price=student.lesson_price)
    
    await callback.message.edit_text(
        "Выберите день недели для регулярного урока:",
        reply_markup=get_days_keyboard(student_id)
    )
    await callback.answer()

@students_router.callback_query(AddSlotFSM.day_of_week, F.data.startswith("add_slot_day_"))
async def cb_add_slot_choose_day(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    student_id = int(parts[3])
    day_idx = int(parts[4])
    await state.update_data(day_of_week=day_idx)
    await state.set_state(AddSlotFSM.time_str)

    await callback.message.edit_text(
        f"Выбран день: <b>{DAYS_FULL[day_idx]}</b>.\n\n"
        f"Введите время начала урока в формате <b>ЧЧ:ММ</b> (например: <i>16:30</i> или <i>18:00</i>):",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(f"student_slots_{student_id}")
    )
    await callback.answer()

@students_router.message(AddSlotFSM.time_str)
async def process_slot_time(message: Message, state: FSMContext):
    time_str = message.text.strip()
    match = re.match(r"^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$", time_str)
    if not match:
        await message.answer("Неверный формат времени. Введите в формате ЧЧ:ММ (например, 17:00):")
        return

    hours, minutes = int(match.group(1)), int(match.group(2))
    slot_time = time(hour=hours, minute=minutes)
    await state.update_data(time_str=slot_time.strftime("%H:%M"))
    await state.set_state(AddSlotFSM.subject)

    data = await state.get_data()
    def_sub = data.get("default_subject", "")

    await message.answer(
        f"📚 <b>Предмет для этого дня занятий</b>\n\n"
        f"Введите название предмета (например: <i>Математика</i> или <i>Физика</i>).\n"
        f"Или отправьте <b>-</b>, чтобы оставить: <i>{def_sub}</i>",
        parse_mode="HTML"
    )

@students_router.message(AddSlotFSM.subject)
async def process_slot_subject(message: Message, state: FSMContext):
    sub = message.text.strip()
    data = await state.get_data()
    if sub == "-":
        sub = data.get("default_subject", "")
    await state.update_data(subject=sub)
    await state.set_state(AddSlotFSM.price)

    def_pr = data.get("default_price", 0.0)
    await message.answer(
        f"💰 <b>Стоимость урока в этот день</b>\n\n"
        f"Введите цену в рублях (например: <i>1500</i> или <i>2000</i>).\n"
        f"Или отправьте <b>-</b>, чтобы оставить базовую ставку: <i>{def_pr:,.0f} ₽</i>",
        parse_mode="HTML"
    )

@students_router.message(AddSlotFSM.price)
async def process_slot_price(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    
    if text == "-":
        price = data.get("default_price", 0.0)
    else:
        try:
            price = float(text.replace(" ", "").replace(",", "."))
        except ValueError:
            await message.answer("Пожалуйста, введите положительное число или '-' для базовой цены:")
            return

    student_id = data["student_id"]
    day_of_week = data["day_of_week"]
    t_parts = data["time_str"].split(":")
    slot_time = time(hour=int(t_parts[0]), minute=int(t_parts[1]))
    subj = data["subject"]

    await StudentService.add_recurring_slot(
        student_id=student_id,
        day_of_week=day_of_week,
        start_time=slot_time,
        duration=60,
        subject=subj,
        price=price
    )
    await state.clear()

    await LessonService.generate_lessons_from_slots(message.from_user.id, days_ahead=14)

    student = await StudentService.get_student_by_id(student_id, message.from_user.id)
    await message.answer(
        f"✅ Регулярный слот <b>{DAYS_FULL[day_of_week]} в {slot_time.strftime('%H:%M')}</b> [{subj}] ({price:,.0f} ₽) успешно добавлен!",
        parse_mode="HTML",
        reply_markup=get_student_card_keyboard(student)
    )

# --- Внесение оплаты ---

@students_router.callback_query(F.data.startswith("student_pay_"))
async def cb_pay_start(callback: CallbackQuery, state: FSMContext):
    student_id = int(callback.data.split("_")[2])
    student = await StudentService.get_student_by_id(student_id, callback.from_user.id)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return

    await state.update_data(student_id=student_id, billing_type=student.billing_type)
    
    if student.billing_type == "package":
        await state.set_state(PaymentFSM.lessons_count)
        text = (
            f"📦 <b>Пополнение пакета уроков для {student.name}</b>\n\n"
            f"Введите <b>количество оплаченных уроков</b> (например: <i>4</i> или <i>8</i>):"
        )
    elif student.billing_type == "postpaid_weekly":
        await state.set_state(PaymentFSM.amount)
        due_text = f" (к оплате за неделю: {abs(student.balance_rub):,.0f} ₽)" if student.balance_rub < 0 else ""
        text = (
            f"🗓 <b>Оплата за неделю для {student.name}</b>{due_text}\n\n"
            f"Введите <b>внесенную сумму</b> в рублях (например: <i>{abs(student.balance_rub):.0f}</i>):"
        )
    else:
        await state.set_state(PaymentFSM.amount)
        text = (
            f"💳 <b>Пополнение баланса для {student.name}</b>\n\n"
            f"Введите <b>внесенную сумму</b> в рублях (например: <i>3000</i>):"
        )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(f"student_view_{student_id}")
    )
    await callback.answer()

@students_router.message(PaymentFSM.lessons_count)
async def process_payment_lessons(message: Message, state: FSMContext):
    try:
        lessons_count = int(message.text.strip())
        if lessons_count <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите положительное целое число уроков (например: 8):")
        return

    data = await state.get_data()
    student_id = data["student_id"]
    student = await StudentService.get_student_by_id(student_id, message.from_user.id)
    
    amount = lessons_count * student.lesson_price
    await FinanceService.record_payment(
        tutor_id=message.from_user.id,
        student_id=student_id,
        amount=amount,
        lessons_count=lessons_count,
        comment=f"Оплата абонемента на {lessons_count} ур."
    )
    await state.clear()

    await message.answer(
        f"✅ <b>Оплата зафиксирована!</b>\n\n"
        f"Ученик: <b>{student.name}</b>\n"
        f"Добавлено уроков: <b>{lessons_count} шт.</b>\n"
        f"Сумма: <b>{amount:,.0f} ₽</b>\n"
        f"Осталось предоплаченных уроков: <b>{student.prepaid_lessons_left + lessons_count} шт.</b>",
        parse_mode="HTML",
        reply_markup=get_student_card_keyboard(student)
    )

@students_router.message(PaymentFSM.amount)
async def process_payment_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(" ", "").replace(",", "."))
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введите положительную сумму в рублях (например: 3000):")
        return

    data = await state.get_data()
    student_id = data["student_id"]
    student = await StudentService.get_student_by_id(student_id, message.from_user.id)

    comment = "Оплата за неделю" if student.billing_type == "postpaid_weekly" else "Пополнение баланса"

    await FinanceService.record_payment(
        tutor_id=message.from_user.id,
        student_id=student_id,
        amount=amount,
        lessons_count=0,
        comment=comment
    )
    await state.clear()

    new_bal = student.balance_rub + amount
    await message.answer(
        f"✅ <b>Оплата успешно внесена!</b>\n\n"
        f"Ученик: <b>{student.name}</b>\n"
        f"Внесено: <b>{amount:,.0f} ₽</b>\n"
        f"Текущий баланс: <b>{new_bal:+.0f} ₽</b>",
        parse_mode="HTML",
        reply_markup=get_student_card_keyboard(student)
    )
