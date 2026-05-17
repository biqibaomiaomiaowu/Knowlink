from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_script(script: str, *, env: dict[str, str] | None = None) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | (env or {}),
    )
    return json.loads(result.stdout)


def test_app_import_in_dramatiq_mode_keeps_worker_and_broker_lazy():
    payload = _run_script(
        """
import json
import sys

from server.app import app

routes = sorted(getattr(route, "path", "") for route in app.routes)
print(json.dumps({
    "parse_start": "/api/v1/courses/{courseId}/parse/start" in routes,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
""",
        env={"KNOWLINK_TASK_QUEUE": "dramatiq"},
    )

    assert payload == {
        "parse_start": True,
        "worker_imported": False,
        "broker_imported": False,
        "dramatiq_imported": False,
    }


def test_worker_actor_uses_configured_redis_broker_and_queue_without_connecting():
    payload = _run_script(
        """
import json

from server.tasks.worker import parse_pipeline

connection_kwargs = parse_pipeline.broker.client.connection_pool.connection_kwargs
print(json.dumps({
    "actor_name": parse_pipeline.actor_name,
    "queue_name": parse_pipeline.queue_name,
    "broker_class": parse_pipeline.broker.__class__.__name__,
    "redis_host": connection_kwargs["host"],
    "redis_port": connection_kwargs["port"],
    "redis_db": connection_kwargs["db"],
}))
""",
        env={
            "KNOWLINK_DRAMATIQ_QUEUE": "contract_parse",
            "KNOWLINK_REDIS_URL": "redis://redis.invalid:6380/12",
        },
    )

    assert payload == {
        "actor_name": "parse_pipeline",
        "queue_name": "contract_parse",
        "broker_class": "RedisBroker",
        "redis_host": "redis.invalid",
        "redis_port": 6380,
        "redis_db": 12,
    }


def test_worker_import_fails_fast_for_insecure_production_settings():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import server.tasks.worker",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "KNOWLINK_ENV": "production",
            "KNOWLINK_STORAGE_BACKEND": "minio",
            "KNOWLINK_DEMO_TOKEN": "knowlink-demo-token",
            "KNOWLINK_MINIO_ACCESS_KEY": "minioadmin",
            "KNOWLINK_MINIO_SECRET_KEY": "minioadmin",
            "KNOWLINK_TASK_QUEUE": "dramatiq",
        },
    )

    assert result.returncode != 0
    assert "Insecure production settings" in result.stderr
    assert "KNOWLINK_DEMO_TOKEN" in result.stderr
    assert "KNOWLINK_MINIO_ACCESS_KEY" in result.stderr
    assert "KNOWLINK_MINIO_SECRET_KEY" in result.stderr


def test_parse_pipeline_actor_invokes_runner_without_broker_send(monkeypatch):
    from server.tasks import worker

    calls: list[dict[str, object]] = []

    def fake_run_parse_pipeline(message, **kwargs):
        calls.append(dict(message))

    monkeypatch.setattr(worker, "run_parse_pipeline", fake_run_parse_pipeline)

    result = worker.parse_pipeline.fn({"taskId": 7, "courseId": 11, "parseRunId": 13})

    assert result is None
    assert calls == [{"taskId": 7, "courseId": 11, "parseRunId": 13}]


def test_handout_generate_actor_invokes_runner_without_broker_send(monkeypatch):
    from server.tasks import worker

    calls: list[dict[str, object]] = []

    def fake_run_handout_generate(message):
        calls.append(dict(message))

    monkeypatch.setattr(worker, "run_handout_generate", fake_run_handout_generate)

    result = worker.handout_generate.fn(
        {
            "taskId": 7,
            "courseId": 11,
            "handoutVersionId": 17,
            "sourceParseRunId": 13,
        }
    )

    assert result is None
    assert calls == [
        {
            "taskId": 7,
            "courseId": 11,
            "handoutVersionId": 17,
            "sourceParseRunId": 13,
        }
    ]


def test_handout_block_generate_actor_invokes_runner_without_broker_send(monkeypatch):
    from server.tasks import worker

    calls: list[dict[str, object]] = []

    def fake_run_handout_block_generate(message):
        calls.append(dict(message))

    monkeypatch.setattr(worker, "run_handout_block_generate", fake_run_handout_block_generate)

    result = worker.handout_block_generate.fn(
        {
            "taskId": 7,
            "courseId": 11,
            "handoutVersionId": 17,
            "handoutBlockId": 19,
            "sourceParseRunId": 13,
        }
    )

    assert result is None
    assert calls == [
        {
            "taskId": 7,
            "courseId": 11,
            "handoutVersionId": 17,
            "handoutBlockId": 19,
            "sourceParseRunId": 13,
        }
    ]


def test_quiz_generate_actor_invokes_runner_without_broker_send(monkeypatch):
    from server.tasks import worker

    calls: list[dict[str, object]] = []

    def fake_run_quiz_generate(message):
        calls.append(dict(message))

    monkeypatch.setattr(worker, "run_quiz_generate", fake_run_quiz_generate)

    result = worker.quiz_generate.fn(
        {
            "taskId": 7,
            "courseId": 11,
            "quizId": 23,
            "questionCountLevel": "small",
        }
    )

    assert result is None
    assert calls == [
        {
            "taskId": 7,
            "courseId": 11,
            "quizId": 23,
            "questionCountLevel": "small",
        }
    ]


def test_review_refresh_actor_invokes_runner_without_broker_send(monkeypatch):
    from server.tasks import worker

    calls: list[dict[str, object]] = []

    def fake_run_review_refresh(message):
        calls.append(dict(message))

    monkeypatch.setattr(worker, "run_review_refresh", fake_run_review_refresh)

    result = worker.review_refresh.fn(
        {
            "taskId": 7,
            "courseId": 11,
            "reviewTaskRunId": 29,
        }
    )

    assert result is None
    assert calls == [
        {
            "taskId": 7,
            "courseId": 11,
            "reviewTaskRunId": 29,
        }
    ]


def test_dramatiq_dispatcher_sends_to_lazy_actor_path_without_redis():
    payload = _run_script(
        """
import json
import sys
import types

sent = []

class FakeActor:
    def send(self, message):
        sent.append(message)

module = types.ModuleType("fake_worker_actor")
module.parse_pipeline = FakeActor()
sys.modules[module.__name__] = module

from server.tasks.dispatcher import DramatiqTaskDispatcher

dispatcher = DramatiqTaskDispatcher(parse_pipeline_actor_path="fake_worker_actor:parse_pipeline")
dispatcher.enqueue_parse_pipeline(
    task_id=23,
    payload={"courseId": 29, "parseRunId": 31, "resourceTypes": ["pdf"]},
)
print(json.dumps({
    "sent": sent,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    )

    assert payload == {
        "sent": [{"taskId": 23, "courseId": 29, "parseRunId": 31, "resourceTypes": ["pdf"]}],
        "worker_imported": False,
        "broker_imported": False,
        "dramatiq_imported": False,
    }


def test_dramatiq_dispatcher_sends_handout_generate_to_lazy_actor_path_without_redis():
    payload = _run_script(
        """
import json
import sys
import types

sent = []

class FakeActor:
    def send(self, message):
        sent.append(message)

module = types.ModuleType("fake_worker_actor")
module.handout_generate = FakeActor()
sys.modules[module.__name__] = module

from server.tasks.dispatcher import DramatiqTaskDispatcher

dispatcher = DramatiqTaskDispatcher(handout_generate_actor_path="fake_worker_actor:handout_generate")
dispatcher.enqueue_handout_generate(
    task_id=23,
    payload={"courseId": 29, "handoutVersionId": 37, "sourceParseRunId": 31},
)
print(json.dumps({
    "sent": sent,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    )

    assert payload == {
        "sent": [{"taskId": 23, "courseId": 29, "handoutVersionId": 37, "sourceParseRunId": 31}],
        "worker_imported": False,
        "broker_imported": False,
        "dramatiq_imported": False,
    }


def test_dramatiq_dispatcher_sends_handout_block_generate_to_lazy_actor_path_without_redis():
    payload = _run_script(
        """
import json
import sys
import types

sent = []

class FakeActor:
    def send(self, message):
        sent.append(message)

module = types.ModuleType("fake_worker_actor")
module.handout_block_generate = FakeActor()
sys.modules[module.__name__] = module

from server.tasks.dispatcher import DramatiqTaskDispatcher

dispatcher = DramatiqTaskDispatcher(handout_block_generate_actor_path="fake_worker_actor:handout_block_generate")
dispatcher.enqueue_handout_block_generate(
    task_id=23,
    payload={"courseId": 29, "handoutVersionId": 37, "handoutBlockId": 41, "sourceParseRunId": 31},
)
print(json.dumps({
    "sent": sent,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    )

    assert payload == {
        "sent": [
            {
                "taskId": 23,
                "courseId": 29,
                "handoutVersionId": 37,
                "handoutBlockId": 41,
                "sourceParseRunId": 31,
            }
        ],
        "worker_imported": False,
        "broker_imported": False,
        "dramatiq_imported": False,
    }


def test_dramatiq_dispatcher_sends_quiz_generate_to_lazy_actor_path_without_redis():
    payload = _run_script(
        """
import json
import sys
import types

sent = []

class FakeActor:
    def send(self, message):
        sent.append(message)

module = types.ModuleType("fake_worker_actor")
module.quiz_generate = FakeActor()
sys.modules[module.__name__] = module

from server.tasks.dispatcher import DramatiqTaskDispatcher

dispatcher = DramatiqTaskDispatcher(quiz_generate_actor_path="fake_worker_actor:quiz_generate")
dispatcher.enqueue_quiz_generate(
    task_id=23,
    payload={"courseId": 29, "quizId": 43, "questionCountLevel": "large"},
)
print(json.dumps({
    "sent": sent,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    )

    assert payload == {
        "sent": [{"taskId": 23, "courseId": 29, "quizId": 43, "questionCountLevel": "large"}],
        "worker_imported": False,
        "broker_imported": False,
        "dramatiq_imported": False,
    }


def test_dramatiq_dispatcher_sends_review_refresh_to_lazy_actor_path_without_redis():
    payload = _run_script(
        """
import json
import sys
import types

sent = []

class FakeActor:
    def send(self, message):
        sent.append(message)

module = types.ModuleType("fake_worker_actor")
module.review_refresh = FakeActor()
sys.modules[module.__name__] = module

from server.tasks.dispatcher import DramatiqTaskDispatcher

dispatcher = DramatiqTaskDispatcher(review_refresh_actor_path="fake_worker_actor:review_refresh")
dispatcher.enqueue_review_refresh(
    task_id=23,
    payload={"courseId": 29, "reviewTaskRunId": 47},
)
print(json.dumps({
    "sent": sent,
    "worker_imported": "server.tasks.worker" in sys.modules,
    "broker_imported": "server.tasks.broker" in sys.modules,
    "dramatiq_imported": "dramatiq" in sys.modules,
}))
"""
    )

    assert payload == {
        "sent": [{"taskId": 23, "courseId": 29, "reviewTaskRunId": 47}],
        "worker_imported": False,
        "broker_imported": False,
        "dramatiq_imported": False,
    }


def test_compose_worker_uses_dramatiq_cli_and_queue_env():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "command: python -m server.tasks.worker" not in compose
    assert "command: dramatiq --processes 1 --threads 4 server.tasks.broker:broker server.tasks.worker" in compose
    assert compose.count("KNOWLINK_TASK_QUEUE: dramatiq") >= 2
    assert compose.count("KNOWLINK_DRAMATIQ_QUEUE: parse_pipeline") >= 2
    assert "KNOWLINK_PARSE_PIPELINE_ACTOR: server.tasks.worker:parse_pipeline" in compose


def test_default_compose_does_not_start_placeholder_scheduler():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "\n  scheduler:" not in compose
    assert "command: python -m server.tasks.scheduler" not in compose


def test_scheduler_contract_is_disabled_by_default():
    from server.tasks.scheduler import build_scheduler_contract

    contract = build_scheduler_contract({})

    assert contract == {
        "enabled": False,
        "jobs": [],
        "message": "KnowLink scheduler is disabled. Set KNOWLINK_SCHEDULER_ENABLED=true to run scheduled jobs.",
    }


def test_compose_real_env_path_runs_migration_and_minio_bucket_init_before_api():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "db-migrate:" in compose
    assert "command: alembic upgrade head" in compose
    assert "minio-init:" in compose
    assert "command: python scripts/init_minio_bucket.py" in compose
    assert "db-migrate:\n        condition: service_completed_successfully" in compose
    assert "minio-init:\n        condition: service_completed_successfully" in compose
    assert "pg_isready -U knowlink -d knowlink" in compose
    assert compose.count("KNOWLINK_MINIO_INTERNAL_ENDPOINT: ${KNOWLINK_MINIO_INTERNAL_ENDPOINT:-minio:9000}") >= 3
    assert (
        compose.count("KNOWLINK_MINIO_PUBLIC_ENDPOINT: ${KNOWLINK_MINIO_PUBLIC_ENDPOINT:-127.0.0.1:9000}")
        >= 3
    )
    assert 'MINIO_API_CORS_ALLOW_ORIGIN: "${KNOWLINK_MINIO_CORS_ALLOW_ORIGIN:-*}"' in compose
