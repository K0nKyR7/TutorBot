from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from config import settings
from database.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        # Создаем таблицы, если их нет
        await conn.run_sync(Base.metadata.create_all)
        
        # Автоматическая миграция новых колонок для существующих таблиц (PostgreSQL / SQLite)
        migration_sqls = [
            "ALTER TABLE recurring_slots ADD COLUMN IF NOT EXISTS subject VARCHAR(255);",
            "ALTER TABLE recurring_slots ADD COLUMN IF NOT EXISTS price DOUBLE PRECISION;",
            "ALTER TABLE lessons ADD COLUMN IF NOT EXISTS subject VARCHAR(255);",
            "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS daily_digest_enabled BOOLEAN DEFAULT TRUE;",
            "ALTER TABLE tutors ADD COLUMN IF NOT EXISTS digest_hour INTEGER DEFAULT 8;"
        ]
        
        for sql in migration_sqls:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
