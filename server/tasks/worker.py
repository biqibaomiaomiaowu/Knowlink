from __future__ import annotations

import time
import dramatiq

# 导入 broker（会自动 set_broker）
from server.tasks.broker import redis_broker  # noqa

from server.infra.db.session import SessionLocal

# 导入新写的、支持 ParseRun 和 VectorDocument 的 Repository
from server.infra.repositories.course_repo import SqlAlchemyCourseRepository

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
