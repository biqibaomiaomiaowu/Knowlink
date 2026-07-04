from __future__ import annotations

import hashlib
from typing import Any

from server.domain.repositories import (
    AsyncTaskRepository,
    CourseRepository,
    HandoutRepository,
    IdempotencyRepository,
    LessonRepository,
    QuizRepository,
    ResourceRepository,
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
        handouts: HandoutRepository | None = None,
        resources: ResourceRepository | None = None,
        task_dispatcher: TaskDispatcher | None = None,
        async_tasks: AsyncTaskRepository | None = None,
    ) -> None:
        self.courses = courses
        self.quizzes = quizzes
        self.idempotency = idempotency
        self.lessons = lessons
        self.scoped_artifacts = scoped_artifacts
        self.handouts = handouts
        self.resources = resources
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
                    "scopeType": "course",
                    "lessonId": None,
                    "startLessonId": None,
                    "endLessonId": None,
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
        lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        try:
            quiz_payload = _build_scoped_objective_quiz_payload(
                course_id=course_id,
                scope_type="lesson",
                lesson=lesson,
                sources=self._lesson_quiz_sources(course_id=course_id, lesson=lesson),
                question_count_level=question_count_level,
            )
            quiz = self.quizzes.create_scoped_quiz(
                course_id=course_id,
                scope_type="lesson",
                lesson_id=lesson_id,
                question_count_level=question_count_level,
                quiz_payload=quiz_payload,
            )
        except ValueError as exc:
            raise self._service_error_from_value_error(exc) from exc
        return self._scoped_quiz_response(quiz)

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
        action = result.get("recommendedReviewAction")
        result.setdefault("recommendedReviewActions", [action] if action else [])
        result["items"] = _public_quiz_attempt_items(
            result.get("items") if isinstance(result.get("items"), list) else quiz_attempt_result.get("items", [])
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
                "quiz.not_ready": 409,
            }.get(error_code, 400),
        )

    def _lesson_quiz_sources(self, *, course_id: int, lesson: dict[str, object]) -> list[dict[str, object]]:
        lesson_id = _int_value(lesson.get("lessonId"))
        if lesson_id is None:
            return []

        handout_sources: list[dict[str, object]] = []
        if self.handouts is not None:
            handout = self.handouts.get_latest_handout(course_id, scope_type="lesson", lesson_id=lesson_id)
            if handout is not None:
                blocks = [block for block in list(handout.get("blocks") or []) if isinstance(block, dict)]
                ready_blocks = [
                    block
                    for block in blocks
                    if block.get("status") == "ready" or block.get("generationStatus") == "ready"
                ]
                for block in ready_blocks:
                    source = _source_from_handout_block(block)
                    if source is not None:
                        handout_sources.append(source)
        if handout_sources:
            return handout_sources

        if self.resources is None:
            return []
        return [
            source
            for resource in self.resources.list_resources(course_id)
            if resource.get("scopeType") == "lesson" and resource.get("lessonId") == lesson_id
            for source in [_source_from_lesson_resource(resource, lesson=lesson)]
            if source is not None
        ]


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


def _build_scoped_objective_quiz_payload(
    *,
    course_id: int,
    scope_type: str,
    lesson: dict[str, Any],
    sources: list[dict[str, object]],
    question_count_level: str,
) -> dict[str, Any]:
    count_by_level = {"small": 1, "medium": 3, "large": 5}
    question_count = count_by_level.get(question_count_level)
    if question_count is None:
        raise ValueError("quiz.not_ready")

    lesson_id = int(lesson["lessonId"])
    lesson_title = str(lesson.get("title") or f"Lesson {lesson_id}")
    if not sources:
        raise ValueError("quiz.not_ready")
    questions = []
    for index in range(1, question_count + 1):
        source = sources[(index - 1) % len(sources)]
        knowledge_point_name = str(source["knowledgePointName"])
        evidence_text = str(source.get("evidenceText") or knowledge_point_name)
        correct_answer = _scoped_correct_answer(
            lesson_id=lesson_id,
            question_index=index,
            source_key=str(source["sourceBlockKey"]),
        )
        options = _scoped_options(
            correct_answer=correct_answer,
            correct_text=evidence_text,
            knowledge_point_name=knowledge_point_name,
        )
        questions.append(
            {
                "questionKey": f"lesson-{lesson_id}-q{index}",
                "questionType": "single_choice",
                "stemMd": f"Which statement best matches {knowledge_point_name} in {lesson_title}?",
                "options": options,
                "correctAnswer": correct_answer,
                "explanationMd": f"The answer is grounded in {knowledge_point_name} evidence from the lesson scope.",
                "difficultyLevel": "medium",
                "knowledgePointKey": str(source["knowledgePointKey"]),
                "knowledgePointName": knowledge_point_name,
                "sourceBlockKey": str(source["sourceBlockKey"]),
                "sourceSegmentKeys": list(source.get("sourceSegmentKeys") or []),
            }
        )

    return {
        "quizType": "scoped_lesson_objective",
        "scopeType": scope_type,
        "courseId": course_id,
        "lessonId": lesson_id,
        "questions": questions,
    }


def _source_from_handout_block(block: dict[str, Any]) -> dict[str, object] | None:
    if block.get("status") != "ready" and block.get("generationStatus") != "ready":
        return None
    block_key = _stable_text(block.get("blockId")) or _stable_text(block.get("outlineKey"))
    if block_key is None:
        return None
    content_md = _stable_text(block.get("contentMd"))
    if content_md is None:
        return None
    source_segment_keys = _stable_text_list(block.get("sourceSegmentKeys"))
    for citation in [item for item in list(block.get("citations") or []) if isinstance(item, dict)]:
        segment_key = _stable_text(citation.get("segmentKey"))
        if segment_key and segment_key not in source_segment_keys:
            source_segment_keys.append(segment_key)
    knowledge_points = [item for item in list(block.get("knowledgePoints") or []) if isinstance(item, dict)]
    first_point = knowledge_points[0] if knowledge_points else {}
    knowledge_point_key = (
        _stable_text(first_point.get("knowledgePointKey"))
        or _stable_text(first_point.get("key"))
        or f"block-{block_key}"
    )
    knowledge_point_name = (
        _stable_text(first_point.get("displayName"))
        or _stable_text(first_point.get("name"))
        or _stable_text(block.get("title"))
        or f"Block {block_key}"
    )
    return {
        "sourceBlockKey": block_key,
        "sourceSegmentKeys": source_segment_keys,
        "knowledgePointKey": knowledge_point_key,
        "knowledgePointName": knowledge_point_name,
        "evidenceText": content_md,
    }


def _source_from_lesson_resource(resource: dict[str, Any], *, lesson: dict[str, object]) -> dict[str, object] | None:
    resource_id = _int_value(resource.get("resourceId"))
    if resource_id is None:
        return None
    lesson_title = str(lesson.get("title") or "Lesson")
    resource_name = _stable_text(resource.get("originalName")) or f"resource {resource_id}"
    source_key = f"resource-{resource_id}"
    source_segment_keys: list[str] = []
    segments = [item for item in list(resource.get("segments") or []) if isinstance(item, dict)]
    evidence_text = None
    for segment in segments:
        segment_key = _stable_text(segment.get("segmentKey"))
        if segment_key and segment_key not in source_segment_keys:
            source_segment_keys.append(segment_key)
        if evidence_text is None:
            evidence_text = _stable_text(segment.get("textContent")) or _stable_text(segment.get("plainText"))
    if evidence_text is None:
        return None
    return {
        "sourceBlockKey": source_key,
        "sourceSegmentKeys": source_segment_keys,
        "knowledgePointKey": source_key,
        "knowledgePointName": f"{lesson_title} {resource_name}",
        "evidenceText": evidence_text,
    }


def _public_quiz_attempt_items(items: object) -> list[dict[str, object]]:
    if not isinstance(items, list):
        return []
    public_items: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        public_item: dict[str, object] = {
            "questionKey": str(item.get("questionKey") or item.get("question_key") or ""),
            "selectedOption": str(item.get("selectedOption") or item.get("selected_option") or ""),
            "isCorrect": bool(item.get("isCorrect") if "isCorrect" in item else item.get("is_correct", False)),
            "obtainedScore": _int_value(item.get("obtainedScore") or item.get("obtained_score")) or 0,
            "explanationMd": str(item.get("explanationMd") or item.get("explanation_md") or ""),
            "knowledgePointKey": str(item.get("knowledgePointKey") or item.get("knowledge_point_key") or ""),
            "sourceBlockKey": str(item.get("sourceBlockKey") or item.get("source_block_key") or ""),
        }
        question_id = _int_value(item.get("questionId") or item.get("question_id"))
        if question_id is not None:
            public_item["questionId"] = question_id
        public_items.append(public_item)
    return public_items


def _scoped_correct_answer(*, lesson_id: int, question_index: int, source_key: str) -> str:
    digest = hashlib.sha256(f"{lesson_id}:{question_index}:{source_key}".encode("utf-8")).digest()
    return ("A", "B", "C", "D")[digest[0] % 4]


def _scoped_options(*, correct_answer: str, correct_text: str, knowledge_point_name: str) -> list[str]:
    distractors = [
        f"{knowledge_point_name} means the process must scan every item before using any structure.",
        f"{knowledge_point_name} means ordering and relationships do not affect the result.",
        f"{knowledge_point_name} means the same rule applies even when the evidence describes a different case.",
    ]
    labels = ["A", "B", "C", "D"]
    output: list[str] = []
    distractor_index = 0
    for label in labels:
        if label == correct_answer:
            text = correct_text
        else:
            text = distractors[distractor_index]
            distractor_index += 1
        output.append(f"{label}. {text}")
    return output


def _stable_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _stable_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _stable_text(item)
        if text and text not in items:
            items.append(text)
    return items
