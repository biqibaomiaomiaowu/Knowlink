from __future__ import annotations

from typing import Any

import dramatiq

from server.config.settings import get_settings
from server.infra.storage import build_object_storage
from server.tasks.broker import get_dramatiq_queue_name, list_registered_tasks
from server.tasks.handouts import run_handout_block_generate, run_handout_generate
from server.tasks.parse_pipeline import run_parse_pipeline
from server.tasks.quizzes import run_quiz_generate
from server.tasks.reviews import run_review_refresh


def _validate_worker_startup_settings() -> None:
    get_settings()


_validate_worker_startup_settings()


@dramatiq.actor(queue_name=get_dramatiq_queue_name())
def parse_pipeline(message: dict[str, Any]) -> None:
    run_parse_pipeline(message, object_storage=build_object_storage(get_settings()))


@dramatiq.actor(queue_name=get_dramatiq_queue_name())
def handout_generate(message: dict[str, Any]) -> None:
    run_handout_generate(message)


@dramatiq.actor(queue_name=get_dramatiq_queue_name())
def handout_block_generate(message: dict[str, Any]) -> None:
    run_handout_block_generate(message)


@dramatiq.actor(queue_name=get_dramatiq_queue_name())
def quiz_generate(message: dict[str, Any]) -> None:
    run_quiz_generate(message)


@dramatiq.actor(queue_name=get_dramatiq_queue_name())
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

from server.ai.vector_projection import build_vector_document_inputs
from server.ai.embedding import embed_texts

# 解析任务
@dramatiq.actor(queue_name="parse")
def parse_pipeline_task(parse_run_id: int):
    print(f"[worker] start parse_run_id={parse_run_id}")

    db = SessionLocal()
    repo = SqlAlchemyCourseRepository(db)

    try:
        # running
        repo.mark_parse_running(parse_run_id)

        #调用解析 Pipeline 得到讲义大纲
        outline_data = run_parse_pipeline(parse_run_id) 
        repo.save_handout_outline(parse_run_id, outline_data)

        #向量投影链路
        vector_inputs = build_vector_document_inputs(parse_run_id)
        texts = [item.text for item in vector_inputs]
        embeddings = embed_texts(texts)
        repo.insert_vector_documents(parse_run_id, vector_inputs, embeddings)

        # succeeded
        repo.mark_parse_succeeded(parse_run_id)
        print(f"[worker] finished parse_run_id={parse_run_id}")

    except Exception as e:
        print(f"[worker] error: {e}")
        repo.mark_parse_failed(parse_run_id, str(e))
        raise

    finally:
        db.close()
