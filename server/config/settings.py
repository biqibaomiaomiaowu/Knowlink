from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str
    env: str
    host: str
    port: int
    demo_token: str
    demo_user_id: int
    demo_user_name: str
    database_url: str
    redis_url: str
    storage_backend: str
    minio_endpoint: str
    minio_internal_endpoint: str
    minio_public_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    course_catalog_path: Path
    runtime_repository_backend: str


@lru_cache
def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[1]
    return Settings(
        app_name=os.getenv("KNOWLINK_APP_NAME", "KnowLink API"),
        env=os.getenv("KNOWLINK_ENV", "development"),
        host=os.getenv("KNOWLINK_HOST", "0.0.0.0"),
        port=int(os.getenv("KNOWLINK_PORT", "8000")),
        demo_token=os.getenv("KNOWLINK_DEMO_TOKEN", "knowlink-demo-token"),
        demo_user_id=int(os.getenv("KNOWLINK_DEMO_USER_ID", "1")),
        demo_user_name=os.getenv("KNOWLINK_DEMO_USER_NAME", "KnowLink Demo"),
        database_url=os.getenv(
            "KNOWLINK_DATABASE_URL",
            "postgresql://knowlink:knowlink@localhost:5432/knowlink",
        ),
        redis_url=os.getenv("KNOWLINK_REDIS_URL", "redis://localhost:6379/0"),
        storage_backend=os.getenv("KNOWLINK_STORAGE_BACKEND", "demo"),
        minio_endpoint=os.getenv("KNOWLINK_MINIO_ENDPOINT", "localhost:9000"),
        minio_internal_endpoint=os.getenv(
            "KNOWLINK_MINIO_INTERNAL_ENDPOINT",
            os.getenv("KNOWLINK_MINIO_ENDPOINT", "localhost:9000"),
        ),
        minio_public_endpoint=os.getenv(
            "KNOWLINK_MINIO_PUBLIC_ENDPOINT",
            os.getenv("KNOWLINK_MINIO_ENDPOINT", "localhost:9000"),
        ),
        minio_access_key=os.getenv("KNOWLINK_MINIO_ACCESS_KEY", "minioadmin"),
        minio_secret_key=os.getenv("KNOWLINK_MINIO_SECRET_KEY", "minioadmin"),
        minio_bucket=os.getenv("KNOWLINK_MINIO_BUCKET", "knowlink"),
        minio_secure=_env_bool("KNOWLINK_MINIO_SECURE", False),
        course_catalog_path=base_dir / "seeds" / "course_catalog.json",
        runtime_repository_backend=os.getenv("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", "memory"),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
