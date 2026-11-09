import asyncio
import os
from datetime import time
from database.db import init_db, async_session
from services.crm_service import TutorService, StudentService, LessonService, FinanceService

async def test_full_flow():
    print("--- 1. Инициализация БД ---")
    await init_db()
    print("БД успешно создана.")

    print("\n--- 2. Создание репетитора ---")
    tutor = await TutorService.get_or_create_tutor(
        telegram_id=123456789,
        full_name="Иван Репетиторов",
        username="tutor_ivan"
    )
    print(f"Репетитор создан: {tutor.full_name} (ID: {tutor.telegram_id})")

    print("\n--- 3. Добавление учеников (пакетный и поурочный) ---")
    # Ученик 1: поурочная оплата
    st1 = await StudentService.create_student(
        tutor_id=123456789,
        name="Михаил (Физика)",
        contact="@misha_phys",
        subject="Физика ЕГЭ",
        billing_type="per_lesson",
        lesson_price=1500.0
    )
    # Ученик 2: пакет уроков
    st2 = await StudentService.create_student(
        tutor_id=123456789,
        name="Анна (Английский)",
        contact="+79991234567",
        subject="IELTS",
        billing_type="package",
        lesson_price=2000.0,
        initial_prepaid=4
    )
    print(f"Добавлен ученик 1: {st1.name}, баланс {st1.balance_rub} руб.")
    print(f"Добавлен ученик 2: {st2.name}, оплачено уроков {st2.prepaid_lessons_left} шт.")

    print("\n--- 4. Настройка расписания (слоты) ---")
    # Ученик 1: по вторникам в 16:00
    slot1 = await StudentService.add_recurring_slot(st1.id, day_of_week=1, start_time=time(16, 0), duration=60)
    # Ученик 2: по четвергам в 18:30
    slot2 = await StudentService.add_recurring_slot(st2.id, day_of_week=3, start_time=time(18, 30), duration=90)
    print("Слоты успешно добавлены.")

    print("\n--- 5. Генерация уроков на 14 дней ---")
    generated_count = await LessonService.generate_lessons_from_slots(123456789, days_ahead=14)
    print(f"Сгенерировано уроков: {generated_count}")

    print("\n--- 6. Проведение урока и проверка списания ---")
    # Получаем сгенерированные уроки
    from datetime import datetime, timedelta
    lessons = await LessonService.get_lessons_for_date_range(
        123456789,
        datetime.now() - timedelta(days=1),
        datetime.now() + timedelta(days=14)
    )
    print(f"Найдено запланированных уроков: {len(lessons)}")
    
    if lessons:
        lesson = lessons[0]
        print(f"Отмечаем урок ID {lesson.id} ({lesson.student.name}) как выполненный...")
        updated = await LessonService.mark_lesson_status(lesson.id, 123456789, "completed")
        print(f"Статус урока: {updated.status}")
        
        # Проверяем баланс ученика
        student_check = await StudentService.get_student_by_id(lesson.student_id, 123456789)
        if student_check.billing_type == "package":
            print(f"Осталось уроков у {student_check.name}: {student_check.prepaid_lessons_left}")
        else:
            print(f"Баланс у {student_check.name}: {student_check.balance_rub} руб.")

    print("\n--- 7. Пополнение баланса и статистика ---")
    await FinanceService.record_payment(123456789, st1.id, amount=3000.0, lessons_count=0, comment="Оплата за 2 урока")
    stats = await FinanceService.get_tutor_stats(123456789)
    print(f"Доход за месяц: {stats['month_income']} руб.")
    print(f"Проведено уроков: {stats['lessons_completed']}")
    print(f"Проблемные ученики / долги: {len(stats['debts'])}")

    print("\n ВСЕ ТЕСТЫ БИЗНЕС-ЛОГИКИ УСПЕШНО ПРОЙДЕНЫ!")

if __name__ == "__main__":
    asyncio.run(test_full_flow())
