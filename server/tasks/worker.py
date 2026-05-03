from __future__ import annotations

from typing import Any

import dramatiq

from server.config.settings import get_settings
from server.infra.storage import build_object_storage
from server.tasks.broker import get_dramatiq_queue_name, list_registered_tasks
from server.tasks.parse_pipeline import run_parse_pipeline


@dramatiq.actor(queue_name=get_dramatiq_queue_name())
def parse_pipeline(message: dict[str, Any]) -> None:
    run_parse_pipeline(message, object_storage=build_object_storage(get_settings()))


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
