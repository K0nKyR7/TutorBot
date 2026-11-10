from datetime import datetime, date, time, timedelta
from typing import List, Optional, Dict
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from database.db import async_session
from database.models import Tutor, Student, RecurringSlot, Lesson, Payment

class TutorService:
    @staticmethod
    async def get_or_create_tutor(telegram_id: int, full_name: str, username: str) -> Tutor:
        async with async_session() as session:
            stmt = select(Tutor).where(Tutor.telegram_id == telegram_id)
            result = await session.execute(stmt)
            tutor = result.scalar_one_or_none()
            if not tutor:
                tutor = Tutor(telegram_id=telegram_id, full_name=full_name, username=username)
                session.add(tutor)
                await session.commit()
                await session.refresh(tutor)
            return tutor

    @staticmethod
    async def get_all_tutors_with_digest() -> List[Tutor]:
        async with async_session() as session:
            stmt = select(Tutor).where(Tutor.daily_digest_enabled == True)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @staticmethod
    async def toggle_daily_digest(telegram_id: int) -> bool:
        async with async_session() as session:
            stmt = select(Tutor).where(Tutor.telegram_id == telegram_id)
            tutor = (await session.execute(stmt)).scalar_one_or_none()
            if tutor:
                tutor.daily_digest_enabled = not tutor.daily_digest_enabled
                await session.commit()
                return tutor.daily_digest_enabled
            return False

class StudentService:
    @staticmethod
    async def create_student(
        tutor_id: int,
        name: str,
        contact: str,
        subject: str,
        billing_type: str,
        lesson_price: float,
        initial_prepaid: int = 0,
        initial_balance: float = 0.0,
        notes: str = ""
    ) -> Student:
        async with async_session() as session:
            student = Student(
                tutor_id=tutor_id,
                name=name,
                contact=contact,
                subject=subject,
                billing_type=billing_type,
                lesson_price=lesson_price,
                prepaid_lessons_left=initial_prepaid,
                balance_rub=initial_balance,
                notes=notes,
                is_active=True
            )
            session.add(student)
            await session.commit()
            await session.refresh(student)
            return student

    @staticmethod
    async def get_tutor_students(tutor_id: int, active_only: bool = True) -> List[Student]:
        async with async_session() as session:
            conditions = [Student.tutor_id == tutor_id]
            if active_only:
                conditions.append(Student.is_active == True)
            stmt = select(Student).where(and_(*conditions)).order_by(Student.name)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @staticmethod
    async def get_student_by_id(student_id: int, tutor_id: int) -> Optional[Student]:
        async with async_session() as session:
            stmt = select(Student).options(
                selectinload(Student.recurring_slots)
            ).where(and_(Student.id == student_id, Student.tutor_id == tutor_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    def calculate_student_plan_income(student: Student) -> Dict[str, float]:
        """
        Считает плановый доход от ученика в неделю и в месяц на основе регулярных слотов или базовой ставки.
        """
        weekly_sum = 0.0
        if student.recurring_slots:
            for slot in student.recurring_slots:
                price = slot.price if slot.price is not None else student.lesson_price
                weekly_sum += price
        else:
            weekly_sum = student.lesson_price
        monthly_sum = weekly_sum * 4.33
        return {
            "weekly": weekly_sum,
            "monthly": monthly_sum
        }

    @staticmethod
    async def update_student_notes(student_id: int, tutor_id: int, notes: str) -> Optional[Student]:
        async with async_session() as session:
            stmt = select(Student).where(and_(Student.id == student_id, Student.tutor_id == tutor_id))
            student = (await session.execute(stmt)).scalar_one_or_none()
            if student:
                student.notes = notes
                await session.commit()
                await session.refresh(student)
            return student

    @staticmethod
    async def toggle_active(student_id: int, tutor_id: int) -> Optional[Student]:
        async with async_session() as session:
            stmt = select(Student).where(and_(Student.id == student_id, Student.tutor_id == tutor_id))
            result = await session.execute(stmt)
            student = result.scalar_one_or_none()
            if student:
                student.is_active = not student.is_active
                await session.commit()
                await session.refresh(student)
            return student

    @staticmethod
    async def delete_student_permanently(student_id: int, tutor_id: int) -> bool:
        async with async_session() as session:
            stmt = select(Student).where(and_(Student.id == student_id, Student.tutor_id == tutor_id))
            student = (await session.execute(stmt)).scalar_one_or_none()
            if student:
                await session.delete(student)
                await session.commit()
                return True
            return False

    @staticmethod
    async def add_recurring_slot(
        student_id: int,
        day_of_week: int,
        start_time: time,
        duration: int = 60,
        subject: Optional[str] = None,
        price: Optional[float] = None
    ) -> RecurringSlot:
        async with async_session() as session:
            slot = RecurringSlot(
                student_id=student_id,
                day_of_week=day_of_week,
                start_time=start_time,
                duration_minutes=duration,
                subject=subject,
                price=price
            )
            session.add(slot)
            await session.commit()
            await session.refresh(slot)
            return slot

    @staticmethod
    async def delete_recurring_slot(slot_id: int):
        async with async_session() as session:
            stmt = select(RecurringSlot).where(RecurringSlot.id == slot_id)
            result = await session.execute(stmt)
            slot = result.scalar_one_or_none()
            if slot:
                await session.delete(slot)
                await session.commit()

class LessonService:
    @staticmethod
    async def create_single_lesson(
        tutor_id: int,
        student_id: int,
        scheduled_at: datetime,
        duration: int = 60,
        subject: Optional[str] = None,
        topic: str = "",
        price: Optional[float] = None
    ) -> Lesson:
        async with async_session() as session:
            st_stmt = select(Student).where(Student.id == student_id)
            st = (await session.execute(st_stmt)).scalar_one_or_none()

            if price is None:
                price = st.lesson_price if st else 0.0
            if subject is None and st:
                subject = st.subject

            lesson = Lesson(
                tutor_id=tutor_id,
                student_id=student_id,
                scheduled_at=scheduled_at,
                duration_minutes=duration,
                subject=subject,
                topic=topic,
                price=price,
                status="scheduled"
            )
            session.add(lesson)
            await session.commit()
            await session.refresh(lesson)
            return lesson

    @staticmethod
    async def get_lessons_for_date_range(tutor_id: int, start_dt: datetime, end_dt: datetime) -> List[Lesson]:
        async with async_session() as session:
            stmt = select(Lesson).options(selectinload(Lesson.student)).where(
                and_(
                    Lesson.tutor_id == tutor_id,
                    Lesson.scheduled_at >= start_dt,
                    Lesson.scheduled_at <= end_dt
                )
            ).order_by(Lesson.scheduled_at)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @staticmethod
    async def get_lesson_by_id(lesson_id: int, tutor_id: int) -> Optional[Lesson]:
        async with async_session() as session:
            stmt = select(Lesson).options(selectinload(Lesson.student)).where(
                and_(Lesson.id == lesson_id, Lesson.tutor_id == tutor_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @staticmethod
    async def update_lesson_materials(lesson_id: int, tutor_id: int, topic: Optional[str] = None, homework: Optional[str] = None):
        async with async_session() as session:
            stmt = select(Lesson).where(and_(Lesson.id == lesson_id, Lesson.tutor_id == tutor_id))
            lesson = (await session.execute(stmt)).scalar_one_or_none()
            if lesson:
                if topic is not None:
                    lesson.topic = topic
                if homework is not None:
                    lesson.homework = homework
                await session.commit()
                await session.refresh(lesson)
            return lesson

    @staticmethod
    async def reschedule_lesson(lesson_id: int, tutor_id: int, new_dt: datetime) -> Optional[Lesson]:
        async with async_session() as session:
            stmt = select(Lesson).where(and_(Lesson.id == lesson_id, Lesson.tutor_id == tutor_id))
            lesson = (await session.execute(stmt)).scalar_one_or_none()
            if lesson:
                lesson.scheduled_at = new_dt
                lesson.status = "scheduled"
                await session.commit()
                await session.refresh(lesson)
            return lesson

    @staticmethod
    async def mark_lesson_status(lesson_id: int, tutor_id: int, status: str) -> Optional[Lesson]:
        async with async_session() as session:
            stmt = select(Lesson).options(selectinload(Lesson.student)).where(
                and_(Lesson.id == lesson_id, Lesson.tutor_id == tutor_id)
            )
            result = await session.execute(stmt)
            lesson = result.scalar_one_or_none()
            if not lesson:
                return None

            prev_status = lesson.status
            lesson.status = status

            # Списание при завершении урока
            if status == "completed" and prev_status != "completed":
                student = lesson.student
                if student:
                    if student.billing_type == "package":
                        student.prepaid_lessons_left -= 1
                    else:
                        student.balance_rub -= lesson.price
                    lesson.is_paid = True
            
            # Отмена списания, если вернули обратно в запланирован или отменен
            elif prev_status == "completed" and status != "completed":
                student = lesson.student
                if student:
                    if student.billing_type == "package":
                        student.prepaid_lessons_left += 1
                    else:
                        student.balance_rub += lesson.price
                    lesson.is_paid = False

            await session.commit()
            await session.refresh(lesson)
            return lesson

    @staticmethod
    async def generate_lessons_from_slots(tutor_id: int, days_ahead: int = 14) -> int:
        now = datetime.now()
        start_date = now.date()
        end_date = start_date + timedelta(days=days_ahead)

        created_count = 0
        async with async_session() as session:
            stmt = select(Student).options(selectinload(Student.recurring_slots)).where(
                and_(Student.tutor_id == tutor_id, Student.is_active == True)
            )
            students = (await session.execute(stmt)).scalars().all()

            for student in students:
                for slot in student.recurring_slots:
                    current = start_date
                    while current <= end_date:
                        if current.weekday() == slot.day_of_week:
                            scheduled_dt = datetime.combine(current, slot.start_time)
                            if scheduled_dt >= now - timedelta(hours=2):
                                check_stmt = select(Lesson).where(
                                    and_(
                                        Lesson.tutor_id == tutor_id,
                                        Lesson.student_id == student.id,
                                        Lesson.scheduled_at == scheduled_dt
                                    )
                                )
                                exists = (await session.execute(check_stmt)).scalar_one_or_none()
                                if not exists:
                                    slot_price = slot.price if slot.price is not None else student.lesson_price
                                    slot_subj = slot.subject if slot.subject else student.subject
                                    lesson = Lesson(
                                        tutor_id=tutor_id,
                                        student_id=student.id,
                                        scheduled_at=scheduled_dt,
                                        duration_minutes=slot.duration_minutes,
                                        subject=slot_subj,
                                        price=slot_price,
                                        status="scheduled"
                                    )
                                    session.add(lesson)
                                    created_count += 1
                        current += timedelta(days=1)
            await session.commit()
        return created_count

class FinanceService:
    @staticmethod
    async def record_payment(tutor_id: int, student_id: int, amount: float, lessons_count: int, comment: str = "") -> Payment:
        async with async_session() as session:
            student_stmt = select(Student).where(and_(Student.id == student_id, Student.tutor_id == tutor_id))
            student = (await session.execute(student_stmt)).scalar_one_or_none()
            if not student:
                raise ValueError("Ученик не найден")

            payment = Payment(
                tutor_id=tutor_id,
                student_id=student_id,
                amount=amount,
                lessons_added=lessons_count,
                comment=comment,
                created_at=datetime.utcnow()
            )
            session.add(payment)

            if student.billing_type == "package":
                student.prepaid_lessons_left += lessons_count
            else:
                student.balance_rub += amount

            await session.commit()
            await session.refresh(payment)
            return payment

    @staticmethod
    async def get_tutor_stats(tutor_id: int):
        async with async_session() as session:
            now = datetime.now()
            start_of_month = datetime(now.year, now.month, 1)

            # Фактический доход за месяц (внесенные оплаты)
            pmt_month = select(func.sum(Payment.amount)).where(
                and_(Payment.tutor_id == tutor_id, Payment.created_at >= start_of_month)
            )
            month_income = (await session.execute(pmt_month)).scalar() or 0.0

            # Фактический доход за последние 7 дней (неделя)
            start_of_week = now - timedelta(days=7)
            pmt_week = select(func.sum(Payment.amount)).where(
                and_(Payment.tutor_id == tutor_id, Payment.created_at >= start_of_week)
            )
            week_income = (await session.execute(pmt_week)).scalar() or 0.0

            # Проведено уроков за месяц
            lessons_stmt = select(func.count(Lesson.id)).where(
                and_(
                    Lesson.tutor_id == tutor_id,
                    Lesson.scheduled_at >= start_of_month,
                    Lesson.status == "completed"
                )
            )
            lessons_completed = (await session.execute(lessons_stmt)).scalar() or 0

            # Все активные ученики со слотами (для расчета планового потенциала)
            students_stmt = select(Student).options(selectinload(Student.recurring_slots)).where(
                and_(Student.tutor_id == tutor_id, Student.is_active == True)
            )
            all_students = (await session.execute(students_stmt)).scalars().all()
            
            planned_weekly_total = 0.0
            debts = []
            for st in all_students:
                plan = StudentService.calculate_student_plan_income(st)
                planned_weekly_total += plan["weekly"]

                if st.billing_type == "package" and st.prepaid_lessons_left <= 0:
                    debts.append((st, f"Осталось уроков: {st.prepaid_lessons_left}"))
                elif st.billing_type == "postpaid_weekly" and st.balance_rub < 0:
                    debts.append((st, f"Постоплата за неделю: {abs(st.balance_rub):.0f} руб."))
                elif st.billing_type == "per_lesson" and st.balance_rub < 0:
                    debts.append((st, f"Долг: {abs(st.balance_rub):.0f} руб."))

            planned_monthly_total = planned_weekly_total * 4.33

            return {
                "month_income": month_income,
                "week_income": week_income,
                "planned_weekly": planned_weekly_total,
                "planned_monthly": planned_monthly_total,
                "lessons_completed": lessons_completed,
                "debts": debts
            }

class ExcelExportService:
    @staticmethod
    async def generate_crm_report(tutor_id: int) -> BytesIO:
        async with async_session() as session:
            # Выгружаем только активных учеников
            students = (await session.execute(
                select(Student).options(selectinload(Student.recurring_slots)).where(
                    and_(Student.tutor_id == tutor_id, Student.is_active == True)
                ).order_by(Student.name)
            )).scalars().all()

            lessons = (await session.execute(
                select(Lesson).options(selectinload(Lesson.student)).where(
                    Lesson.tutor_id == tutor_id
                ).order_by(Lesson.scheduled_at.desc())
            )).scalars().all()

            payments = (await session.execute(
                select(Payment).options(selectinload(Payment.student)).where(
                    Payment.tutor_id == tutor_id
                ).order_by(Payment.created_at.desc())
            )).scalars().all()

        wb = openpyxl.Workbook()
        
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")

        # 1. Лист Ученики
        ws_students = wb.active
        ws_students.title = "Ученики"
        headers_st = [
            "ID", "Имя", "Предмет(ы)", "Контакты", "Тип оплаты", "Базовая ставка (₽)",
            "План в нед. (₽)", "План в мес. (₽)", "Осталось уроков", "Баланс (₽)", "Статус", "Заметки"
        ]
        ws_students.append(headers_st)
        
        for col_num in range(1, len(headers_st) + 1):
            cell = ws_students.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        billing_excel_names = {
            "package": "Пакет",
            "per_lesson": "Поурочно",
            "postpaid_weekly": "Постоплата (в конце недели)"
        }

        for s in students:
            plan = StudentService.calculate_student_plan_income(s)
            ws_students.append([
                s.id,
                s.name,
                s.subject or "-",
                s.contact or "-",
                billing_excel_names.get(s.billing_type, s.billing_type),
                s.lesson_price,
                round(plan["weekly"]),
                round(plan["monthly"]),
                s.prepaid_lessons_left if s.billing_type == "package" else "-",
                s.balance_rub if s.billing_type in ["per_lesson", "postpaid_weekly"] else "-",
                "Активен" if s.is_active else "В архиве",
                s.notes or ""
            ])

        # 2. Лист Уроки
        ws_lessons = wb.create_sheet(title="История уроков")
        headers_les = ["ID", "Дата и время", "Ученик", "Предмет", "Длит. (мин)", "Тема", "ДЗ", "Статус", "Стоимость (₽)"]
        ws_lessons.append(headers_les)
        
        for col_num in range(1, len(headers_les) + 1):
            cell = ws_lessons.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        status_names = {
            "scheduled": "Запланирован",
            "completed": "Проведен",
            "cancelled_by_student": "Отменен учеником",
            "cancelled_by_tutor": "Отменен репетитором"
        }

        for l in lessons:
            ws_lessons.append([
                l.id,
                l.scheduled_at.strftime("%d.%m.%Y %H:%M"),
                l.student.name if l.student else "—",
                l.subject or (l.student.subject if l.student else "-"),
                l.duration_minutes,
                l.topic or "-",
                l.homework or "-",
                status_names.get(l.status, l.status),
                l.price
            ])

        # 3. Лист Платежи
        ws_payments = wb.create_sheet(title="Платежи")
        headers_pay = ["ID", "Дата", "Ученик", "Сумма (₽)", "Добавлено уроков", "Комментарий"]
        ws_payments.append(headers_pay)

        for col_num in range(1, len(headers_pay) + 1):
            cell = ws_payments.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for p in payments:
            ws_payments.append([
                p.id,
                p.created_at.strftime("%d.%m.%Y %H:%M"),
                p.student.name if p.student else "—",
                p.amount,
                p.lessons_added,
                p.comment or ""
            ])

        for sheet in wb.worksheets:
            for col in sheet.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
