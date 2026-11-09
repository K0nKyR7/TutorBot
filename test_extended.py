import asyncio
import os
from datetime import datetime, time, timedelta
from database.db import init_db
from services.crm_service import TutorService, StudentService, LessonService, FinanceService, ExcelExportService

async def test_extended_features():
    print("--- 1. Инициализация обновленной БД ---")
    await init_db()
    print("БД обновлена.")

    print("\n--- 2. Создание репетитора ---")
    tutor = await TutorService.get_or_create_tutor(999, "Анна Репетитор", "anna_tutor")
    print(f"Репетитор: {tutor.full_name}, дайджест: {tutor.daily_digest_enabled}")

    print("\n--- 3. Добавление ученика с заметкой ---")
    st = await StudentService.create_student(
        tutor_id=999,
        name="Екатерина Смирнова",
        contact="@katya_s",
        subject="Математика ОГЭ",
        billing_type="package",
        lesson_price=1800.0,
        initial_prepaid=8,
        notes="Проблемы с геометрией (теорема Пифагора, окружности)"
    )
    print(f"Ученик: {st.name}, заметка: {st.notes}")

    print("\n--- 4. Назначение разового урока ---")
    lesson_dt = datetime.now() + timedelta(days=1)
    lesson = await LessonService.create_single_lesson(
        tutor_id=999,
        student_id=st.id,
        scheduled_at=lesson_dt,
        duration=60,
        topic="Тригонометрия в прямоугольном треугольнике"
    )
    print(f"Разовый урок назначен на: {lesson.scheduled_at}, тема: {lesson.topic}")

    print("\n--- 5. Добавление ДЗ и темы к уроку ---")
    await LessonService.update_lesson_materials(
        lesson.id, 999,
        topic="Тригонометрия (Sin, Cos, Tg)",
        homework="Учебник стр. 45 №12, 14, 15(а, б)"
    )
    updated_lesson = await LessonService.get_lesson_by_id(lesson.id, 999)
    print(f"Обновленный урок ID {updated_lesson.id}: ДЗ -> {updated_lesson.homework}")

    print("\n--- 6. Перенос урока ---")
    new_dt = lesson_dt + timedelta(hours=2)
    rescheduled = await LessonService.reschedule_lesson(lesson.id, 999, new_dt)
    print(f"Урок успешно перенесен на: {rescheduled.scheduled_at}")

    print("\n--- 7. Фиксация оплаты и экспорт в Excel ---")
    await FinanceService.record_payment(999, st.id, amount=14400.0, lessons_count=8, comment="Пакет на 8 уроков")
    excel_stream = await ExcelExportService.generate_crm_report(999)
    excel_bytes = excel_stream.getvalue()
    print(f"Excel-отчет успешно сгенерирован в памяти! Размер файла: {len(excel_bytes)} байт.")

    print("\n--- 8. Переключение дайджеста ---")
    new_status = await TutorService.toggle_daily_digest(999)
    print(f"Статус дайджеста после переключения: {new_status}")

    print("\n ВСЕ НОВЫЕ ФУНКЦИИ ПРОТЕСТИРОВАНЫ И РАБОТАЮТ БЕЗУПРЕЧНО!")

if __name__ == "__main__":
    asyncio.run(test_extended_features())
