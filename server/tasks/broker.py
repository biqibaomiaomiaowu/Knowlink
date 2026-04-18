"""Task registry scaffold for the MVP build."""

from server.tasks.payloads import TASK_PAYLOAD_MODELS


TASK_REGISTRY = {
    name: {
        "payload_model": payload_model,
        "status": "placeholder",
    }
    for name, payload_model in TASK_PAYLOAD_MODELS.items()
}


def list_registered_tasks() -> list[str]:
    return sorted(TASK_REGISTRY)
