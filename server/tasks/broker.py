"""Dramatiq broker and task registry for the runtime worker."""

from __future__ import annotations

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from server.tasks.payloads import TASK_PAYLOAD_MODELS


DEFAULT_DRAMATIQ_QUEUE = "parse_pipeline"


def _get_queue_env(name: str, fallback: str) -> str:
    return os.getenv(name) or fallback


def get_dramatiq_queue_name() -> str:
    return _get_queue_env("KNOWLINK_DRAMATIQ_QUEUE", DEFAULT_DRAMATIQ_QUEUE)


def get_dramatiq_parse_queue_name() -> str:
    return _get_queue_env("KNOWLINK_DRAMATIQ_PARSE_QUEUE", get_dramatiq_queue_name())


def get_dramatiq_content_queue_name() -> str:
    return _get_queue_env("KNOWLINK_DRAMATIQ_CONTENT_QUEUE", get_dramatiq_queue_name())


def get_dramatiq_quiz_queue_name() -> str:
    return _get_queue_env("KNOWLINK_DRAMATIQ_QUIZ_QUEUE", get_dramatiq_queue_name())


def get_dramatiq_review_queue_name() -> str:
    return _get_queue_env("KNOWLINK_DRAMATIQ_REVIEW_QUEUE", get_dramatiq_queue_name())


def get_dramatiq_import_queue_name() -> str:
    return _get_queue_env("KNOWLINK_DRAMATIQ_IMPORT_QUEUE", get_dramatiq_queue_name())


def get_dramatiq_maintenance_queue_name() -> str:
    return _get_queue_env("KNOWLINK_DRAMATIQ_MAINTENANCE_QUEUE", get_dramatiq_queue_name())


def build_redis_broker() -> RedisBroker:
    return RedisBroker(url=os.getenv("KNOWLINK_REDIS_URL", "redis://localhost:6379/0"))


broker = build_redis_broker()
dramatiq.set_broker(broker)


TASK_REGISTRY = {
    name: {
        "payload_model": payload_model,
        "status": "registered",
    }
    for name, payload_model in TASK_PAYLOAD_MODELS.items()
}


def list_registered_tasks() -> list[str]:
    return sorted(TASK_REGISTRY)
