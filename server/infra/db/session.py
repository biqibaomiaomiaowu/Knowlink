from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://knowlink:knowlink@postgres:5432/knowlink"

    class Config:
        env_file = ".env"
        env_prefix = "KNOWLINK_"

settings = Settings()

# 创建异步数据库引擎
engine = create_async_engine(
    settings.database_url,
    echo=False,  # 不想看SQL日志改成 False
    future=True
)

# 创建会话
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)