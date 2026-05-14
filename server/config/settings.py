from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


SUPPORTED_TASK_QUEUES = {"dramatiq", "noop"}
PRODUCTION_LIKE_ENVS = {"production", "prod", "staging"}
UNSAFE_PRODUCTION_STORAGE_BACKENDS = {"", "demo", "disabled", "fake", "local", "memory", "none"}


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
    cors_allow_origins: tuple[str, ...]
    course_catalog_path: Path
    runtime_repository_backend: str
    task_queue: str
    scheduler_enabled: bool


@lru_cache
def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[1]
    settings = Settings(
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
        cors_allow_origins=_env_csv(
            "KNOWLINK_CORS_ALLOW_ORIGINS",
            ("http://localhost:*", "http://127.0.0.1:*"),
        ),
        course_catalog_path=base_dir / "seeds" / "course_catalog.json",
        runtime_repository_backend=os.getenv("KNOWLINK_RUNTIME_REPOSITORY_BACKEND", "memory"),
        task_queue=os.getenv("KNOWLINK_TASK_QUEUE", "dramatiq"),
        scheduler_enabled=_env_bool("KNOWLINK_SCHEDULER_ENABLED", False),
    )
    _validate_task_queue(settings)
    _validate_runtime_hardening(settings)
    return settings


def _validate_task_queue(settings: Settings) -> None:
    queue_mode = settings.task_queue.strip().lower()
    if queue_mode in SUPPORTED_TASK_QUEUES:
        return
    supported = ", ".join(sorted(SUPPORTED_TASK_QUEUES))
    raise RuntimeError(f"Unsupported KNOWLINK_TASK_QUEUE: {settings.task_queue!r}. Supported values: {supported}.")


def _validate_runtime_hardening(settings: Settings) -> None:
    if settings.env.strip().lower() not in PRODUCTION_LIKE_ENVS:
        return

    insecure_names: list[str] = []
    task_queue = settings.task_queue.strip().lower()
    runtime_backend = settings.runtime_repository_backend.strip().lower()
    storage_backend = settings.storage_backend.strip().lower()

    if settings.demo_token.strip() in {"", "knowlink-demo-token"}:
        insecure_names.append("KNOWLINK_DEMO_TOKEN")

    if task_queue == "noop":
        insecure_names.append(f"KNOWLINK_TASK_QUEUE={task_queue}")
    if runtime_backend != "sql":
        insecure_names.append(f"KNOWLINK_RUNTIME_REPOSITORY_BACKEND={runtime_backend}")
    if storage_backend in UNSAFE_PRODUCTION_STORAGE_BACKENDS:
        insecure_names.append(f"KNOWLINK_STORAGE_BACKEND={storage_backend}")

    if storage_backend == "minio":
        if settings.minio_access_key.strip() in {"", "minioadmin"}:
            insecure_names.append("KNOWLINK_MINIO_ACCESS_KEY")
        if settings.minio_secret_key.strip() in {"", "minioadmin"}:
            insecure_names.append("KNOWLINK_MINIO_SECRET_KEY")

    if insecure_names:
        joined = ", ".join(insecure_names)
        raise RuntimeError(
            f"Insecure production settings: {joined} must not use demo/default or data-loss-prone values."
        )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())
