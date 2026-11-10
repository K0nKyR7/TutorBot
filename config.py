import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///tutor_crm.db")
# Render дает ссылки вида postgres:// или postgresql://
# Для асинхронного SQLAlchemy нам нужен драйвер asyncpg: postgresql+asyncpg://
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+asyncpg://"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

class Settings(BaseModel):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DATABASE_URL: str = raw_db_url

settings = Settings()
