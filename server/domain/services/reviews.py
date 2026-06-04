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
        return {"items": self.reviews.list_review_tasks(course_id)}

    def get_lesson_review(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        return {
            "scopeType": "lesson",
            "lessonId": lesson_id,
            "status": "placeholder",
            "items": [self._lesson_review_task(lesson=lesson)],
        }

    def regenerate_lesson_review(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        return self.get_lesson_review(course_id=course_id, lesson_id=lesson_id)

    def get_course_review(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        lessons = self._course_lessons(course_id)
        weak_lessons = [
            {
                "lessonId": lesson["lessonId"],
                "title": lesson.get("title"),
                "masteryScore": lesson.get("masteryScore"),
                "reasonText": "该课时存在待复习知识点占位。",
            }
            for lesson in lessons
        ]
        return {
            "scopeType": "course",
            "lessonId": None,
            "status": "placeholder",
            "items": [],
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
            run = self.reviews.create_review_run(course_id)
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

    def _lesson_review_task(self, *, lesson: dict[str, object]) -> dict[str, object]:
        lesson_id = int(lesson["lessonId"])
        return {
            "reviewTaskId": lesson_id * 10 + 1,
            "taskType": "revisit_lesson",
            "scopeType": "lesson",
            "lessonId": lesson_id,
            "priorityScore": 80,
            "reasonText": "该课时存在待复习知识点占位。",
            "recommendedMinutes": 15,
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
