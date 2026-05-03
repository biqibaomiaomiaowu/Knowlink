from __future__ import annotations

import time
from typing import Any

import dramatiq

from server.tasks.broker import list_registered_tasks
from server.tasks.parse_pipeline import run_parse_pipeline


@dramatiq.actor
def parse_pipeline(message: dict[str, Any]) -> None:
    run_parse_pipeline(message)


def main() -> None:
    registered = ", ".join(list_registered_tasks())
    print(f"KnowLink worker scaffold registered tasks: {registered}")
    while True:
        print("KnowLink worker placeholder is running.")
        time.sleep(60)


if __name__ == "__main__":
    main()
