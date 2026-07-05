from __future__ import annotations

from server.domain.repositories import (
    AsyncTaskRepository,
    CourseRepository,
    IdempotencyRepository,
    LessonRepository,
    ReviewRepository,
    TaskDispatcher,
)
from server.domain.services.async_tasks import (
    enqueue_or_fail_if_missing_dispatcher,
    ensure_async_task_for_trigger,
    raise_async_task_binding_failed,
    refresh_enqueue_failure_status,
    resolve_async_tasks,
)
from server.domain.services.errors import ServiceError
from server.domain.services.idempotency import review_result_matches_course, run_fingerprinted_idempotent


class ReviewService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        reviews: ReviewRepository,
        idempotency: IdempotencyRepository,
        lessons: LessonRepository | None = None,
        task_dispatcher: TaskDispatcher | None = None,
        async_tasks: AsyncTaskRepository | None = None,
    ) -> None:
        self.courses = courses
        self.reviews = reviews
        self.idempotency = idempotency
        self.lessons = lessons
        self.task_dispatcher = task_dispatcher
        self.async_tasks = resolve_async_tasks(async_tasks, reviews)

    def list_review_tasks(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return {"items": self._review_task_views(course_id=course_id)}

    def get_lesson_review(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        task = self._lesson_review_task(lesson=lesson)
        return {
            "scopeType": "lesson",
            "lessonId": lesson_id,
            "status": "placeholder",
            "items": [
                self._review_task_view(
                    course_id=course_id,
                    task=task,
                    lessons_by_id={lesson_id: lesson},
                )
            ],
        }

    def regenerate_lesson_review(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        return self.get_lesson_review(course_id=course_id, lesson_id=lesson_id)

    def get_course_review(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        lessons = self._course_lessons(course_id)
        task_views = self._review_task_views(course_id=course_id, lessons=lessons)
        weak_lessons = [
            {
                "lessonId": lesson["lessonId"],
                "title": lesson.get("title"),
                "masteryScore": lesson.get("masteryScore"),
                "reasonText": "该课时存在待复习知识点占位。",
            }
            for lesson in lessons
        ]
        knowledge_point_keys = {
            str(task["knowledgePointKey"])
            for task in task_views
            if task.get("knowledgePointKey") is not None
        }
        source_question_keys = {
            str(question_key)
            for task in task_views
            for question_key in _list_value(task.get("sourceQuestionKeys"))
            if question_key is not None
        }
        return {
            "scopeType": "course",
            "lessonId": None,
            "status": "placeholder",
            "items": task_views,
            "todayTaskCount": len(task_views),
            "weakPointCount": len(knowledge_point_keys) if knowledge_point_keys else len(weak_lessons),
            "mistakeCount": len(source_question_keys),
            "masteryScore": self._course_mastery_score(lessons),
            "topTasks": task_views[:3],
            "weakLessons": weak_lessons,
            "crossLessonWeakPoints": [
                {
                    "knowledgePointKey": "kp-cross-lesson-placeholder",
                    "title": "跨课时薄弱点占位",
                    "lessonIds": [lesson["lessonId"] for lesson in lessons],
                    "evidenceChain": [
                        {"type": "course_review", "scopeType": "course", "courseId": course_id},
                    ],
                }
            ]
            if lessons
            else [],
        }

    def regenerate_course_review(self, *, course_id: int) -> dict[str, object]:
        return self.get_course_review(course_id=course_id)

    def get_exam_review(self, *, course_id: int) -> dict[str, object]:
        course = self._ensure_course(course_id)
        exam_at = course.get("examAt")
        return {
            "scopeType": "course",
            "lessonId": None,
            "status": "placeholder" if exam_at is not None else "not_generated",
            "examAt": exam_at,
            "items": [],
            "message": "考前复习本轮仅提供占位入口。" if exam_at is not None else "课程尚未设置考试时间。",
            "availableActions": ["open_course_review"] if exam_at is not None else ["set_exam_at"],
            "citations": [],
        }

    def regenerate_review_tasks(
        self,
        *,
        course_id: int,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        self._ensure_course(course_id)
        enqueue_request: tuple[int, dict[str, object]] | None = None
        created_response: dict[str, object] | None = None

        def factory() -> dict[str, object]:
            nonlocal enqueue_request, created_response
            try:
                run = self.reviews.create_review_run(course_id)
            except ValueError as exc:
                if str(exc) == "review.not_ready":
                    return {
                        "taskId": 0,
                        "status": "not_ready",
                        "nextAction": "complete_course_quiz",
                        "entity": {"type": "course", "id": course_id},
                    }
                raise
            missing_refresh_task = object()
            refresh_task = run.pop("_reviewRefreshTask", missing_refresh_task)
            if refresh_task is missing_refresh_task:
                return run
            if not isinstance(refresh_task, dict):
                raise_async_task_binding_failed(
                    self.async_tasks,
                    task_id=None,
                    message="Review refresh task metadata was invalid.",
                )
            task_id = _int_value(refresh_task.get("taskId"))
            if task_id is None:
                raise_async_task_binding_failed(
                    self.async_tasks,
                    task_id=None,
                    message="Review refresh task did not include a task id.",
                )
            payload = refresh_task.get("payload")
            if not isinstance(payload, dict):
                raise_async_task_binding_failed(
                    self.async_tasks,
                    task_id=task_id,
                    message="Review refresh task payload was invalid.",
                )
            review_task_run_id = _int_value(run.get("reviewTaskRunId"))
            if review_task_run_id is None:
                raise_async_task_binding_failed(
                    self.async_tasks,
                    task_id=task_id,
                    message="Review refresh task did not include a review task run id.",
                )
            created_response = {
                "taskId": task_id,
                "status": "queued",
                "nextAction": "poll",
                "entity": {"type": "review_task_run", "id": review_task_run_id},
            }
            created_response, task_id = ensure_async_task_for_trigger(
                self.async_tasks,
                created_response,
                course_id=course_id,
                task_type="review_refresh",
                payload=payload,
                target_type="review_task_run",
                target_id=review_task_run_id,
                allow_create=True,
            )
            if task_id is None:
                raise_async_task_binding_failed(
                    self.async_tasks,
                    task_id=None,
                    message="Review refresh task could not be bound.",
                )
            enqueue_request = (task_id, payload)
            return created_response

        result = run_fingerprinted_idempotent(
            self.idempotency,
            scope=f"reviews.regenerate:{course_id}",
            key=idempotency_key,
            request_payload={"courseId": course_id},
            factory=factory,
            legacy_action="reviews.regenerate",
            legacy_matches=lambda legacy: review_result_matches_course(
                legacy,
                course_id=course_id,
                async_tasks=self.async_tasks,
            ),
        )
        if enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            enqueue_or_fail_if_missing_dispatcher(
                self.async_tasks,
                task_id=task_id,
                dispatcher=self.task_dispatcher,
                enqueue=lambda: self.task_dispatcher.enqueue_review_refresh(task_id=task_id, payload=payload),
            )
        if isinstance(result, dict) and self.async_tasks is not None:
            return refresh_enqueue_failure_status(self.async_tasks, result)
        return result

    def get_review_run_status(self, *, review_task_run_id: int) -> dict[str, object]:
        run = self.reviews.get_review_run(review_task_run_id)
        if run is None:
            raise ServiceError(
                message="Review run was not found.",
                error_code="review.run_not_found",
                status_code=404,
            )
        return run

    def complete_review_task(self, *, review_task_id: int) -> dict[str, object]:
        return self.reviews.complete_review_task(review_task_id)

    def _ensure_course(self, course_id: int) -> dict[str, object]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course

    def _ensure_lesson(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        if self.lessons is None:
            raise ServiceError(
                message="Lesson was not found.",
                error_code="lesson.not_found",
                status_code=404,
            )
        lesson = self.lessons.get_lesson(course_id=course_id, lesson_id=lesson_id)
        if lesson is None:
            raise ServiceError(
                message="Lesson was not found.",
                error_code="lesson.not_found",
                status_code=404,
            )
        return lesson

    def _course_lessons(self, course_id: int) -> list[dict[str, object]]:
        if self.lessons is None:
            return []
        return list(self.lessons.list_lessons(course_id))

    def _review_task_views(
        self,
        *,
        course_id: int,
        lessons: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        lessons_by_id = {
            int(lesson["lessonId"]): lesson
            for lesson in (lessons if lessons is not None else self._course_lessons(course_id))
            if lesson.get("lessonId") is not None
        }
        tasks = list(self.reviews.list_review_tasks(course_id))
        task_views = [
            self._review_task_view(course_id=course_id, task=task, lessons_by_id=lessons_by_id)
            for task in tasks
            if self._is_pending_review_task(task)
            and self._has_core_review_task_fields(task)
        ]
        return sorted(
            task_views,
            key=lambda task: (
                _int_value(task.get("reviewOrder")) or 9999,
                -(_int_value(task.get("priorityScore")) or 0),
                _int_value(task.get("reviewTaskId")) or 0,
            ),
        )

    def _review_task_view(
        self,
        *,
        course_id: int,
        task: dict[str, object],
        lessons_by_id: dict[int, dict[str, object]],
    ) -> dict[str, object]:
        view = dict(task)
        review_task_id = _int_value(view.get("reviewTaskId"))
        if view.get("completionSupported") is False:
            view["taskId"] = None
        elif review_task_id is not None:
            view["taskId"] = review_task_id
        lesson_id = _int_value(view.get("lessonId"))
        lesson = lessons_by_id.get(lesson_id) if lesson_id is not None else None
        view["sourceLesson"] = self._source_lesson_view(lesson)
        linked_block_id = self._linked_handout_block_id(view)
        view["linkedHandoutBlockId"] = linked_block_id
        view["recommendedAction"] = self._recommended_action(view, linked_block_id=linked_block_id)
        view["jumpRoute"] = self._jump_route(course_id=course_id, lesson_id=lesson_id)
        if view.get("recommendedHandoutBlock") is None and linked_block_id is not None:
            view["recommendedHandoutBlock"] = {"blockId": linked_block_id}
        return view

    def _is_pending_review_task(self, task: dict[str, object]) -> bool:
        return task.get("status") not in {"completed", "superseded", "canceled", "cancelled"}

    def _has_core_review_task_fields(self, task: dict[str, object]) -> bool:
        if _int_value(task.get("reviewTaskId")) is None:
            return False
        if _text_value(task.get("taskType")) is None:
            return False
        if _int_value(task.get("priorityScore")) is None:
            return False
        if _text_value(task.get("reasonText")) is None:
            return False
        return _int_value(task.get("recommendedMinutes")) is not None

    def _source_lesson_view(self, lesson: dict[str, object] | None) -> dict[str, object] | None:
        if lesson is None:
            return None
        return {
            "lessonId": lesson.get("lessonId"),
            "title": lesson.get("title"),
            "masteryScore": lesson.get("masteryScore"),
        }

    def _linked_handout_block_id(self, task: dict[str, object]) -> int | None:
        direct = _int_value(task.get("linkedHandoutBlockId"))
        if direct is not None:
            return direct
        for container_key in ("recommendedHandoutBlock", "recommendedAction", "recommendedSegment"):
            container = task.get(container_key)
            if not isinstance(container, dict):
                continue
            for value_key in ("blockId", "handoutBlockId", "targetBlockId", "targetBlockKey"):
                value = _int_value(container.get(value_key))
                if value is not None:
                    return value
        return _int_value(task.get("sourceBlockKey"))

    def _recommended_action(self, task: dict[str, object], *, linked_block_id: int | None) -> dict[str, object]:
        action = task.get("recommendedAction")
        if isinstance(action, dict):
            return action
        task_type = str(task.get("taskType") or "revisit_block")
        label = "Review weak point" if task_type == "revisit_block" else "Continue review"
        result: dict[str, object] = {"type": task_type, "label": label}
        if linked_block_id is not None:
            result["targetBlockId"] = linked_block_id
        return result

    def _jump_route(self, *, course_id: int, lesson_id: int | None) -> str:
        if lesson_id is not None:
            return f"/courses/{course_id}/lessons/{lesson_id}/handout"
        return f"/courses/{course_id}/review"

    def _course_mastery_score(self, lessons: list[dict[str, object]]) -> float | None:
        scores = [float(lesson["masteryScore"]) for lesson in lessons if lesson.get("masteryScore") is not None]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 4)

    def _lesson_review_task(self, *, lesson: dict[str, object]) -> dict[str, object]:
        lesson_id = int(lesson["lessonId"])
        return {
            "reviewTaskId": -(lesson_id * 10 + 1),
            "taskType": "revisit_lesson",
            "scopeType": "lesson",
            "lessonId": lesson_id,
            "priorityScore": 80,
            "reasonText": "该课时存在待复习知识点占位。",
            "recommendedMinutes": 15,
            "completionSupported": False,
            "knowledgePointKey": f"lesson-{lesson_id}-placeholder",
            "sourceQuestionKeys": [],
            "recommendedHandoutBlock": None,
            "recommendedSegment": {
                "lessonId": lesson_id,
                "label": "回看本节关键片段",
            },
            "practiceEntry": {
                "type": "lesson_quiz",
                "lessonId": lesson_id,
                "label": "生成本节练习",
            },
            "reviewOrder": 1,
            "intensity": "medium",
            "evidenceChain": [
                {
                    "type": "lesson_review",
                    "scopeType": "lesson",
                    "lessonId": lesson_id,
                    "title": lesson.get("title"),
                }
            ],
        }


def _int_value(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _list_value(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []
