from sqlalchemy.orm import Session
from datetime import datetime

from server.infra.db.models.course import Course
from server.infra.db.models.resource import CourseResource
from server.infra.db.models.parse_run import ParseRun
from server.infra.db.models.async_task import AsyncTask

from server.infra.db.models.course import CourseSegment

class SqlAlchemyRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---------- idempotency ----------
    def run_idempotent(self, action, key, factory):
        return factory()

    # ---------- course ----------
    async def create_course(self, *, title, entry_type, goal_text, preferred_style, catalog_id=None):
        course = Course(
            user_id=1,  # 先写死 demo
            title=title,
            entry_type=entry_type,
            goal_text=goal_text,
            lifecycle_status="draft",
            pipeline_stage="idle",
            pipeline_status="idle",
        )
        self.db.add(course)
        await self.db.commit()
        await self.db.refresh(course)
        return self._course_dict(course)

    async def get_course(self, course_id):
        c = await self.db.get(Course, course_id)
        return self._course_dict(c) if c else None

    def list_recent_courses(self):
        items = self.db.query(Course).order_by(Course.updated_at.desc()).all()
        return [self._course_dict(c) for c in items]

    # ---------- resource ----------
    def create_resource(self, course_id, payload):
        r = CourseResource(
            course_id=course_id,
            resource_type=payload["resourceType"],
            object_key=payload["objectKey"],
            original_name=payload["originalName"],
            mime_type=payload["mimeType"],
            ingest_status="ready",
            validation_status="passed",
            processing_status="pending",
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._resource_dict(r)

    def list_resources(self, course_id):
        items = self.db.query(CourseResource).filter_by(course_id=course_id).all()
        return [self._resource_dict(r) for r in items]

    def delete_resource(self, course_id, resource_id):
        r = self.db.query(CourseResource).filter_by(id=resource_id, course_id=course_id).first()
        if not r:
            return False
        self.db.delete(r)
        self.db.commit()
        return True

    # ---------- parse ----------
    def create_parse_run(self, course_id):
        run = ParseRun(
            course_id=course_id,
            status="queued",
            progress_pct=0,
        )
        self.db.add(run)
        self.db.flush()

        task = AsyncTask(
            course_id=course_id,
            parse_run_id=run.id,
            task_type="parse_pipeline",
            status="queued",
            progress_pct=0,
        )
        self.db.add(task)

        course = self.db.get(Course, course_id)
        if course:
            course.pipeline_stage = "parsing"
            course.pipeline_status = "queued"
            course.active_parse_run_id = run.id

        self.db.commit()
        self.db.refresh(run)
        self.db.refresh(task)

        return self._parse_run_dict(run), self._task_dict(task)

    def mark_parse_running(self, parse_run_id):
        run = self.db.get(ParseRun, parse_run_id)
        if not run:
            return

        run.status = "running"
        run.progress_pct = 50
        run.started_at = datetime.utcnow()

        task = self.db.query(AsyncTask).filter_by(parse_run_id=parse_run_id).first()
        if task:
            task.status = "running"
            task.progress_pct = 50

        self.db.commit()

    def mark_parse_succeeded(self, parse_run_id):
        run = self.db.get(ParseRun, parse_run_id)
        if not run:
            return

        run.status = "succeeded"
        run.progress_pct = 100
        run.finished_at = datetime.utcnow()

        task = self.db.query(AsyncTask).filter_by(parse_run_id=parse_run_id).first()
        if task:
            task.status = "succeeded"
            task.progress_pct = 100

        course = self.db.get(Course, run.course_id)
        if course:
            course.lifecycle_status = "inquiry_ready"
            course.pipeline_stage = "inquiry"
            course.pipeline_status = "succeeded"

        self.db.commit()

    # ---------- dto ----------
    def _course_dict(self, c):
        return {
            "courseId": c.id,
            "title": c.title,
            "entryType": c.entry_type,
            "goalText": c.goal_text,
            "lifecycleStatus": c.lifecycle_status,
            "pipelineStage": c.pipeline_stage,
            "pipelineStatus": c.pipeline_status,
        }

    def _resource_dict(self, r):
        return {
            "resourceId": r.id,
            "resourceType": r.resource_type,
            "originalName": r.original_name,
            "objectKey": r.object_key,
            "ingestStatus": r.ingest_status,
            "validationStatus": r.validation_status,
            "processingStatus": r.processing_status,
        }

    def _parse_run_dict(self, r):
        return {
            "parseRunId": r.id,
            "courseId": r.course_id,
            "status": r.status,
            "progressPct": r.progress_pct,
        }

    def _task_dict(self, t):
        return {
            "taskId": t.id,
            "status": t.status,
        }
    

class CourseRepository:
    def __init__(self, session):
        self.session = session

    def save_segments(self, segments: list[CourseSegment]):
        """批量保存解析后的片段"""
        self.session.add_all(segments)
        self.session.commit()

    def update_learning_preference(self, course_id: int, prefs: dict):
        """更新课程的学习偏好 (第二周 Inquiry 环节用)"""
        # 这里的逻辑对应你在第二周要实现的 API
        pass