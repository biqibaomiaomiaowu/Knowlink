from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any


SCHEDULED_JOBS = ("review_refresh", "cache_cleanup", "stuck_task_watchdog")
DISABLED_MESSAGE = "KnowLink scheduler is disabled. Set KNOWLINK_SCHEDULER_ENABLED=true to run scheduled jobs."


def build_scheduler_contract(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    values = os.environ if env is None else env
    enabled = _env_bool(values.get("KNOWLINK_SCHEDULER_ENABLED"))
    return {
        "enabled": enabled,
        "jobs": list(SCHEDULED_JOBS) if enabled else [],
        "message": (
            f"KnowLink scheduler enabled for jobs: {', '.join(SCHEDULED_JOBS)}"
            if enabled
            else DISABLED_MESSAGE
        ),
    }


def main() -> None:
    contract = build_scheduler_contract()
    print(contract["message"])
    if not contract["enabled"]:
        return
    while True:
        print(f"KnowLink scheduler noop tick for jobs: {', '.join(contract['jobs'])}")
        time.sleep(60)


def _env_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    main()
