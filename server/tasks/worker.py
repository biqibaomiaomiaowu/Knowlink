from __future__ import annotations

from typing import Any

import dramatiq

from server.config.settings import get_settings
from server.infra.storage import build_object_storage
from server.tasks.broker import (
    get_dramatiq_content_queue_name,
    get_dramatiq_parse_queue_name,
    get_dramatiq_queue_name,
    list_registered_tasks,
)
from server.tasks.handouts import run_handout_block_generate, run_handout_generate
from server.tasks.parse_pipeline import run_parse_pipeline
from server.tasks.quizzes import run_quiz_generate
from server.tasks.reviews import run_review_refresh


def _validate_worker_startup_settings() -> None:
    get_settings()


_validate_worker_startup_settings()


@dramatiq.actor(queue_name=get_dramatiq_parse_queue_name())
def parse_pipeline(message: dict[str, Any]) -> None:
    run_parse_pipeline(message, object_storage=build_object_storage(get_settings()))


@dramatiq.actor(queue_name=get_dramatiq_content_queue_name())
def handout_generate(message: dict[str, Any]) -> None:
    run_handout_generate(message)


@dramatiq.actor(queue_name=get_dramatiq_content_queue_name())
def handout_block_generate(message: dict[str, Any]) -> None:
    run_handout_block_generate(message)


@dramatiq.actor(queue_name=get_dramatiq_content_queue_name())
def quiz_generate(message: dict[str, Any]) -> None:
    run_quiz_generate(message)


@dramatiq.actor(queue_name=get_dramatiq_content_queue_name())
def review_refresh(message: dict[str, Any]) -> None:
    run_review_refresh(message)


def main() -> None:
    registered = ", ".join(list_registered_tasks())
    queue_name = get_dramatiq_queue_name()
    print(
        "KnowLink Dramatiq actors registered: "
        f"{registered}. Start a worker with: "
        f"dramatiq server.tasks.broker:broker server.tasks.worker --queues {queue_name}"
    )


if __name__ == "__main__":
    main()
