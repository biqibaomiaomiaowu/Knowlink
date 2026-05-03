from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from server.config.settings import get_settings


settings = get_settings()

ASYNC_DATABASE_URL = settings.database_url

SYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace(
    "postgresql+asyncpg://",
    "postgresql+psycopg2://",
)

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)