import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///tutor_crm.db")

# Преобразуем протокол для asyncpg
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif raw_db_url.startswith("postgresql://") and not raw_db_url.startswith("postgresql+asyncpg://"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Для asyncpg удаляем параметры sslmode и channel_binding из query string, так как asyncpg их не парсит как libpq
if "?" in raw_db_url and "asyncpg" in raw_db_url:
    base_url = raw_db_url.split("?")[0]
    raw_db_url = base_url

class Settings(BaseModel):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DATABASE_URL: str = raw_db_url

settings = Settings()
