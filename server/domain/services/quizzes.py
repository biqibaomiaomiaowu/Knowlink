from __future__ import annotations

from server.domain.repositories import (
    AsyncTaskRepository,
    CourseRepository,
    IdempotencyRepository,
    LessonRepository,
    QuizRepository,
    ScopedArtifactRepository,
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
from server.domain.services.idempotency import async_trigger_matches_course, run_fingerprinted_idempotent
from server.ai.quiz_strategy import grade_quiz_attempt
from server.ai.review_strategy import build_mastery_record_updates


class QuizService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        quizzes: QuizRepository,
        idempotency: IdempotencyRepository,
        lessons: LessonRepository | None = None,
        scoped_artifacts: ScopedArtifactRepository | None = None,
        task_dispatcher: TaskDispatcher | None = None,
        async_tasks: AsyncTaskRepository | None = None,
    ) -> None:
        self.courses = courses
        self.quizzes = quizzes
        self.idempotency = idempotency
        self.lessons = lessons
        self.scoped_artifacts = scoped_artifacts
        self.task_dispatcher = task_dispatcher
        self.async_tasks = resolve_async_tasks(async_tasks, quizzes)

    def generate_quiz(
        self,
        *,
        course_id: int,
        question_count_level: str = "medium",
        idempotency_key: str | None,
    ) -> dict[str, object]:
        self._ensure_course(course_id)
        enqueue_request: tuple[int, dict[str, object]] | None = None
        created_response: dict[str, object] | None = None

        def factory() -> dict[str, object]:
            nonlocal enqueue_request, created_response
            try:
                _, trigger = self.quizzes.create_quiz(course_id, question_count_level=question_count_level)
            except ValueError as exc:
                raise ServiceError(
                    message=str(exc),
                    error_code="quiz.not_ready",
                    status_code=409,
                ) from exc
            if _should_enqueue_trigger(trigger):
                task_id = _int_value(trigger.get("taskId"))
                if task_id is None:
                    raise_async_task_binding_failed(
                        self.async_tasks,
                        task_id=None,
                        message="Async task trigger did not include a task id.",
                    )
                quiz_id = _entity_id(trigger)
                if quiz_id is None:
                    raise_async_task_binding_failed(
                        self.async_tasks,
                        task_id=task_id,
                        message="Async task trigger did not include a quiz id.",
                    )
                payload = {
                    "courseId": course_id,
                    "quizId": quiz_id,
                    "questionCountLevel": question_count_level,
                }
                trigger, task_id = ensure_async_task_for_trigger(
                    self.async_tasks,
                    trigger,
                    course_id=course_id,
                    task_type="quiz_generate",
                    payload=payload,
                    target_type="quiz",
                    target_id=quiz_id,
                    allow_create=True,
                )
                if task_id is None:
                    raise_async_task_binding_failed(
                        self.async_tasks,
                        task_id=None,
                        message="Async task trigger could not be bound.",
                    )
                enqueue_request = (task_id, payload)
            created_response = trigger
            return trigger

        result = run_fingerprinted_idempotent(
            self.idempotency,
            scope=f"quizzes.generate:{course_id}",
            key=idempotency_key,
            request_payload={
                "courseId": course_id,
                "questionCountLevel": question_count_level,
            },
            factory=factory,
            legacy_action="quizzes.generate",
            legacy_matches=lambda legacy: async_trigger_matches_course(
                legacy,
                course_id=course_id,
                entity_type="quiz",
                task_type="quiz_generate",
                async_tasks=self.async_tasks,
                target_type="quiz",
            ),
        )
        if enqueue_request is not None and result is created_response:
            task_id, payload = enqueue_request
            enqueue_or_fail_if_missing_dispatcher(
                self.async_tasks,
                task_id=task_id,
                dispatcher=self.task_dispatcher,
                enqueue=lambda: self.task_dispatcher.enqueue_quiz_generate(task_id=task_id, payload=payload),
            )
        if isinstance(result, dict) and self.async_tasks is not None:
            return refresh_enqueue_failure_status(self.async_tasks, result)
        return result

    def get_quiz(self, *, quiz_id: int) -> dict[str, object]:
        quiz = self.quizzes.get_quiz(quiz_id)
        if quiz is None:
            raise ServiceError(
                message="Quiz was not found.",
                error_code="quiz.not_found",
                status_code=404,
            )
        return quiz

    def generate_lesson_quiz(
        self,
        *,
        course_id: int,
        lesson_id: int,
        question_count_level: str = "medium",
    ) -> dict[str, object]:
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        return self._create_scoped_quiz(
            course_id=course_id,
            scope_type="lesson",
            lesson_id=lesson_id,
            question_count_level=question_count_level,
        )

    def get_current_lesson_quiz(self, *, course_id: int, lesson_id: int) -> dict[str, object]:
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        if self.scoped_artifacts is None:
            raise self._artifact_scope_error()
        artifacts = [
            artifact
            for artifact in self.scoped_artifacts.list_lesson_artifacts(course_id=course_id, lesson_id=lesson_id)
            if artifact.get("artifactType") == "quiz"
        ]
        if not artifacts:
            raise ServiceError(
                message="Lesson quiz was not found.",
                error_code="quiz.not_found",
                status_code=404,
            )
        latest = artifacts[-1]
        quiz = self.quizzes.get_quiz(int(latest["artifactId"]))
        return self._scoped_quiz_response(quiz or latest)

    def generate_stage_quiz(self, *, course_id: int, payload) -> dict[str, object]:
        self._ensure_course(course_id)
        self._ensure_lesson(course_id=course_id, lesson_id=payload.start_lesson_id)
        self._ensure_lesson(course_id=course_id, lesson_id=payload.end_lesson_id)
        return self._create_scoped_quiz(
            course_id=course_id,
            scope_type="lesson_range",
            start_lesson_id=payload.start_lesson_id,
            end_lesson_id=payload.end_lesson_id,
            question_count_level=payload.question_count_level,
        )

    def generate_comprehensive_quiz(
        self,
        *,
        course_id: int,
        question_count_level: str = "medium",
    ) -> dict[str, object]:
        self._ensure_course(course_id)
        return self._create_scoped_quiz(
            course_id=course_id,
            scope_type="course",
            question_count_level=question_count_level,
        )

    def subjective_grading_placeholder(self, *, course_id: int) -> dict[str, object]:
        self._ensure_course(course_id)
        return {
            "answerText": None,
            "gradingStatus": "placeholder",
            "totalScore": None,
            "dimensionScores": [],
            "deductions": [],
            "feedbackMd": "主观题 AI 判卷本轮仅提供合同占位，不运行正式 judge。",
            "citations": [],
            "confidenceScore": None,
            "needsHumanReview": False,
        }

    def get_quiz_status(self, *, quiz_id: int) -> dict[str, object]:
        quiz = self.get_quiz(quiz_id=quiz_id)
        return {
            "quizId": quiz["quizId"],
            "status": quiz["status"],
            "questionCount": quiz["questionCount"],
        }

    def submit_quiz(self, *, quiz_id: int, payload) -> dict[str, object]:
        quiz = self.quizzes.get_quiz(quiz_id)
        if quiz is None:
            raise ServiceError(
                message="Quiz was not found.",
                error_code="quiz.not_found",
                status_code=404,
            )
        if quiz.get("status") != "ready":
            raise ServiceError(
                message="Quiz is not ready for attempts.",
                error_code="quiz.not_ready",
                status_code=409,
            )
        answers = payload.model_dump(by_alias=True, exclude_none=True).get("answers", [])
        context = self.quizzes.get_quiz_submission_context(quiz_id)
        if context is None:
            raise ServiceError(
                message="Quiz was not found.",
                error_code="quiz.not_found",
                status_code=404,
            )
        quiz_payload = context.get("quizPayload")
        if not isinstance(quiz_payload, dict):
            raise ServiceError(
                message="Quiz submission context was invalid.",
                error_code="quiz.context_invalid",
                status_code=500,
            )
        existing_records = context.get("masteryRecords", [])
        if not isinstance(existing_records, list):
            existing_records = []
        quiz_attempt_result = grade_quiz_attempt(quiz_payload, answers)
        mastery_updates = build_mastery_record_updates(
            quiz_attempt_result,
            existing_records=existing_records,
        )
        result = dict(
            self.quizzes.save_quiz_attempt_result(
                quiz_id,
                quiz_attempt_result=quiz_attempt_result,
                mastery_updates=mastery_updates,
            )
        )
        missing_refresh_task = object()
        refresh_task = result.pop("_reviewRefreshTask", missing_refresh_task)
        if refresh_task is not missing_refresh_task:
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
            review_task_run_id = _int_value(payload.get("reviewTaskRunId"))
            if review_task_run_id is None:
                raise_async_task_binding_failed(
                    self.async_tasks,
                    task_id=task_id,
                    message="Review refresh task did not include a review task run id.",
                )
            course_id = _int_value(payload.get("courseId")) or _int_value(quiz.get("courseId"))
            trigger = {
                "taskId": task_id,
                "status": "queued",
                "nextAction": "poll",
                "entity": {"type": "review_task_run", "id": review_task_run_id},
            }
            _, task_id = ensure_async_task_for_trigger(
                self.async_tasks,
                trigger,
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
            enqueue_or_fail_if_missing_dispatcher(
                self.async_tasks,
                task_id=task_id,
                dispatcher=self.task_dispatcher,
                enqueue=lambda: self.task_dispatcher.enqueue_review_refresh(task_id=task_id, payload=payload),
            )
        return result

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

    def _create_scoped_quiz(
        self,
        *,
        course_id: int,
        scope_type: str,
        lesson_id: int | None = None,
        start_lesson_id: int | None = None,
        end_lesson_id: int | None = None,
        question_count_level: str,
    ) -> dict[str, object]:
        if self.scoped_artifacts is None:
            raise self._artifact_scope_error()
        try:
            artifact = self.scoped_artifacts.create_scoped_artifact(
                artifact_type="quiz",
                course_id=course_id,
                scope_type=scope_type,
                lesson_id=lesson_id,
                start_lesson_id=start_lesson_id,
                end_lesson_id=end_lesson_id,
                status="placeholder",
                quizMode="objective",
                questionCountLevel=question_count_level,
            )
        except ValueError as exc:
            raise self._service_error_from_value_error(exc) from exc
        quiz = self.quizzes.get_quiz(int(artifact["artifactId"]))
        return self._scoped_quiz_response(quiz or artifact)

    def _scoped_quiz_response(self, quiz: dict[str, object]) -> dict[str, object]:
        quiz_id = quiz.get("quizId", quiz.get("artifactId"))
        return {
            "quizId": quiz_id,
            "courseId": quiz.get("courseId"),
            "scopeType": quiz.get("scopeType", "course"),
            "lessonId": quiz.get("lessonId"),
            "startLessonId": quiz.get("startLessonId"),
            "endLessonId": quiz.get("endLessonId"),
            "quizMode": quiz.get("quizMode", "objective"),
            "status": quiz.get("status", "placeholder"),
            "questionCount": quiz.get("questionCount", 0),
            "questions": list(quiz.get("questions") or []),
        }

    def _artifact_scope_error(self) -> ServiceError:
        return ServiceError(
            message="Scoped quiz artifacts are unavailable.",
            error_code="artifact.scope_invalid",
            status_code=400,
        )

    def _service_error_from_value_error(self, exc: ValueError) -> ServiceError:
        error_code = str(exc) or "artifact.scope_invalid"
        return ServiceError(
            message=error_code.replace(".", " "),
            error_code=error_code,
            status_code={
                "artifact.scope_invalid": 400,
                "lesson.not_found": 404,
                "course.not_found": 404,
            }.get(error_code, 400),
        )


def _int_value(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _entity_id(trigger: dict[str, object]) -> int | None:
    entity = trigger.get("entity")
    if not isinstance(entity, dict):
        return None
    return _int_value(entity.get("id"))


def _should_enqueue_trigger(trigger: dict[str, object]) -> bool:
    return trigger.get("status") == "queued" and trigger.get("nextAction") == "poll"
