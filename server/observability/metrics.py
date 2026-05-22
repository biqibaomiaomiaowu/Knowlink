from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)


if "REGISTRY" not in globals():
    REGISTRY = CollectorRegistry()

if "HTTP_REQUESTS_TOTAL" not in globals():
    HTTP_REQUESTS_TOTAL = Counter(
        "knowlink_http_requests_total",
        "HTTP requests",
        ["method", "route", "status_code"],
        registry=REGISTRY,
    )
if "HTTP_REQUEST_DURATION_SECONDS" not in globals():
    HTTP_REQUEST_DURATION_SECONDS = Histogram(
        "knowlink_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "route"],
        registry=REGISTRY,
    )
if "ASYNC_TASKS_TOTAL" not in globals():
    ASYNC_TASKS_TOTAL = Counter(
        "knowlink_async_tasks_total",
        "Async task lifecycle events",
        ["task_type", "status"],
        registry=REGISTRY,
    )
if "ASYNC_TASK_ENQUEUE_DURATION_SECONDS" not in globals():
    ASYNC_TASK_ENQUEUE_DURATION_SECONDS = Histogram(
        "knowlink_async_task_enqueue_duration_seconds",
        "Async task enqueue latency",
        ["task_type", "adapter"],
        registry=REGISTRY,
    )


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
