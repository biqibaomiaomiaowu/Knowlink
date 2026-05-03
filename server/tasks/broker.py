"""Dramatiq broker and task registry for the runtime worker."""

from __future__ import annotations

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from server.tasks.payloads import TASK_PAYLOAD_MODELS


DEFAULT_DRAMATIQ_QUEUE = "parse_pipeline"


def get_dramatiq_queue_name() -> str:
    return os.getenv("KNOWLINK_DRAMATIQ_QUEUE", DEFAULT_DRAMATIQ_QUEUE)


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
