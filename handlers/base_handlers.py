from datetime import datetime, date, time
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from services.crm_service import TutorService, FinanceService, LessonService, ExcelExportService
from keyboards.crm_keyboards import get_main_menu, get_settings_keyboard

base_router = Router()

@base_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    tutor = await TutorService.get_or_create_tutor(
        telegram_id=user.id,
        full_name=user.full_name,
        username=user.username or ""
    )

    welcome_text = (
        f"👋 Здравствуйте, <b>{user.first_name}</b>!\n\n"
        f"Добро пожаловать в <b>TutorCRM</b> — профессионального бота-помощника для репетиторов.\n\n"
        f"<b>Возможности системы:</b>\n"
        f"• 👥 <b>Ученики:</b> карточки, контакты, заметки, гибкая оплата\n"
        f"• 📅 <b>Расписание:</b> регулярные слоты и разовые уроки\n"
        f"• 📝 <b>Учебный процесс:</b> запись тем и домашних заданий\n"
        f"• 💰 <b>Финансы:</b> учет абонементов, баланса и долгов\n"
        f"• 📊 <b>Экспорт:</b> моментальная выгрузка всей базы в Excel\n"
        f"• 🔔 <b>Утренний дайджест:</b> расписание уроков каждое утро в 08:00\n\n"
        f"Выберите раздел в меню ниже:"
    )

    await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_main_menu())

@base_router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Главное меню TutorCRM</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@base_router.callback_query(F.data == "menu_finance")
async def cb_finance(callback: CallbackQuery):
    stats = await FinanceService.get_tutor_stats(callback.from_user.id)
    
    text = (
        f"📊 <b>Финансы и статистика за текущий месяц</b>\n\n"
        f"💰 <b>Получено оплат:</b> {stats['month_income']:,.0f} ₽\n"
        f"🎓 <b>Проведено уроков:</b> {stats['lessons_completed']} шт.\n\n"
    )

    debts = stats["debts"]
    if debts:
        text += "⚠️ <b>Внимание (долги / закончились уроки в абонементе):</b>\n"
        for st, note in debts:
            text += f"• <b>{st.name}</b> ({st.subject or 'без предмета'}): {note}\n"
    else:
        text += "✅ <i>Все ученики оплачены, долгов нет!</i>"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@base_router.callback_query(F.data == "menu_export_excel")
async def cb_export_excel(callback: CallbackQuery):
    await callback.answer("Генерирую Excel-отчет...")
    excel_file = await ExcelExportService.generate_crm_report(callback.from_user.id)
    
    today_str = date.today().strftime("%d_%m_%Y")
    filename = f"TutorCRM_Report_{today_str}.xlsx"
    
    input_file = BufferedInputFile(excel_file.getvalue(), filename=filename)
    await callback.message.answer_document(
        input_file,
        caption=f"📊 <b>Ваш актуальный отчет TutorCRM</b>\nСодержит вкладки: <i>Ученики</i>, <i>История уроков</i> и <i>Платежи</i>.",
        parse_mode="HTML"
    )

@base_router.callback_query(F.data == "menu_settings")
async def cb_settings(callback: CallbackQuery):
    user = callback.from_user
    tutor = await TutorService.get_or_create_tutor(user.id, user.full_name, user.username or "")
    
    await callback.message.edit_text(
        "⚙️ <b>Настройки сервиса</b>\n\n"
        "Вы можете включить или отключить ежедневный утренний дайджест (в 08:00 МСК бот будет присылать план уроков на день):",
        parse_mode="HTML",
        reply_markup=get_settings_keyboard(tutor.daily_digest_enabled)
    )
    await callback.answer()

@base_router.callback_query(F.data == "settings_toggle_digest")
async def cb_toggle_digest(callback: CallbackQuery):
    is_enabled = await TutorService.toggle_daily_digest(callback.from_user.id)
    status_msg = "Утренний дайджест включен!" if is_enabled else "Утренний дайджест отключен."
    await callback.answer(status_msg, show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(is_enabled))
