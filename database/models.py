from datetime import datetime, time
from sqlalchemy import (
    BigInteger, Integer, String, Float, Boolean, DateTime, Time, ForeignKey, Text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Tutor(Base):
    __tablename__ = "tutors"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    daily_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_hour: Mapped[int] = mapped_column(Integer, default=8)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    students = relationship("Student", back_populates="tutor", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="tutor", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="tutor", cascade="all, delete-orphan")

class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tutor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tutors.telegram_id"))
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact: Mapped[str] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # billing_type: "per_lesson", "package", "postpaid_weekly"
    billing_type: Mapped[str] = mapped_column(String(50), default="per_lesson")
    lesson_price: Mapped[float] = mapped_column(Float, default=0.0) # Базовая ставка
    
    prepaid_lessons_left: Mapped[int] = mapped_column(Integer, default=0)
    balance_rub: Mapped[float] = mapped_column(Float, default=0.0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tutor = relationship("Tutor", back_populates="students")
    recurring_slots = relationship("RecurringSlot", back_populates="student", cascade="all, delete-orphan")
    lessons = relationship("Lesson", back_populates="student", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="student", cascade="all, delete-orphan")

class RecurringSlot(Base):
    __tablename__ = "recurring_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"))
    
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False) # 0..6
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    
    # Предмет и цена конкретно для этого слота (если отличаются от базовой ставки ученика)
    subject: Mapped[str] = mapped_column(String(255), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=True)

    student = relationship("Student", back_populates="recurring_slots")

class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tutor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tutors.telegram_id"))
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"))
    
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    subject: Mapped[str] = mapped_column(String(255), nullable=True) # Конкретный предмет урока
    topic: Mapped[str] = mapped_column(String(255), nullable=True)   # Тема урока
    homework: Mapped[str] = mapped_column(Text, nullable=True)       # Домашнее задание

    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    price: Mapped[float] = mapped_column(Float, default=0.0)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)

    tutor = relationship("Tutor", back_populates="lessons")
    student = relationship("Student", back_populates="lessons")

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tutor_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tutors.telegram_id"))
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"))
    
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    lessons_added: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    comment: Mapped[str] = mapped_column(String(255), nullable=True)

    tutor = relationship("Tutor", back_populates="payments")
    student = relationship("Student", back_populates="payments")
