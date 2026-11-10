from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import Student, Lesson

DAYS_OF_WEEK = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAYS_FULL = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

def get_main_menu():
    kb = [
        [
            InlineKeyboardButton(text="📅 Расписание", callback_data="menu_schedule"),
            InlineKeyboardButton(text="👥 Ученики", callback_data="menu_students")
        ],
        [
            InlineKeyboardButton(text="💰 Финансы & Отчет", callback_data="menu_finance"),
            InlineKeyboardButton(text="📊 Экспорт в Excel", callback_data="menu_export_excel")
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки & Дайджест", callback_data="menu_settings")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_students_menu(students: list[Student]):
    kb = []
    for s in students:
        status_icon = "🟢" if s.is_active else "⚪️"
        if s.billing_type == "package":
            bal_str = f"[{s.prepaid_lessons_left} ур.]"
        elif s.billing_type == "postpaid_weekly":
            bal_str = f"[к оплате: {abs(s.balance_rub):.0f} ₽]" if s.balance_rub < 0 else f"[{s.balance_rub:+.0f} ₽]"
        else:
            bal_str = f"[{s.balance_rub:+.0f} ₽]"
        kb.append([
            InlineKeyboardButton(
                text=f"{status_icon} {s.name} {bal_str}",
                callback_data=f"student_view_{s.id}"
            )
        ])
    
    kb.append([InlineKeyboardButton(text="➕ Добавить ученика", callback_data="student_add")])
    kb.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_student_card_keyboard(student: Student):
    kb = [
        [
            InlineKeyboardButton(text="💳 Внести оплату", callback_data=f"student_pay_{student.id}"),
            InlineKeyboardButton(text="🗓 Расписание уроков", callback_data=f"student_slots_{student.id}")
        ],
        [
            InlineKeyboardButton(text="➕ Назначить разовый урок", callback_data=f"lesson_add_single_{student.id}")
        ],
        [
            InlineKeyboardButton(text="📝 Изменить заметку", callback_data=f"student_notes_{student.id}"),
            InlineKeyboardButton(
                text="📦 В архив" if student.is_active else "🔄 Восстановить",
                callback_data=f"student_toggle_{student.id}"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 К списку учеников", callback_data="menu_students")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_schedule_menu():
    kb = [
        [
            InlineKeyboardButton(text="📍 Сегодня", callback_data="sched_today"),
            InlineKeyboardButton(text="📍 Завтра", callback_data="sched_tomorrow")
        ],
        [
            InlineKeyboardButton(text="📆 На этой неделе", callback_data="sched_week"),
            InlineKeyboardButton(text="🔄 Сгенерировать слоты", callback_data="sched_generate")
        ],
        [
            InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_lesson_action_keyboard(lesson: Lesson):
    kb = [
        [
            InlineKeyboardButton(text="✅ Проведен", callback_data=f"lesson_status_{lesson.id}_completed"),
            InlineKeyboardButton(text="❌ Отменен", callback_data=f"lesson_status_{lesson.id}_cancelled_by_student")
        ],
        [
            InlineKeyboardButton(text="📝 Тема / Домашка", callback_data=f"lesson_hw_{lesson.id}"),
            InlineKeyboardButton(text="🕒 Перенести", callback_data=f"lesson_reschedule_{lesson.id}")
        ],
        [
            InlineKeyboardButton(text="🔙 К расписанию", callback_data="menu_schedule")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_days_keyboard(student_id: int):
    kb = []
    row = []
    for idx, day in enumerate(DAYS_OF_WEEK):
        row.append(InlineKeyboardButton(text=day, callback_data=f"add_slot_day_{student_id}_{idx}"))
        if len(row) == 4:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="🔙 Отмена", callback_data=f"student_view_{student_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_settings_keyboard(digest_enabled: bool):
    digest_status = "Включен 🔔" if digest_enabled else "Выключен 🔕"
    kb = [
        [
            InlineKeyboardButton(text=f"Утренний дайджест (08:00): {digest_status}", callback_data="settings_toggle_digest")
        ],
        [
            InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_cancel_keyboard(callback_data: str = "main_menu"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=callback_data)]]
    )
