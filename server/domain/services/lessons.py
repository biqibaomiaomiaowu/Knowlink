from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from server.domain.repositories import (
    CourseRepository,
    LessonProgressRepository,
    LessonRepository,
    ResourceRepository,
    ScopedArtifactRepository,
)
from server.domain.services.errors import ServiceError


VIDEO_RESOURCE_TYPES = {"mp4"}


class LessonService:
    def __init__(
        self,
        *,
        courses: CourseRepository,
        lessons: LessonRepository,
        resources: ResourceRepository,
        lesson_progress: LessonProgressRepository,
        scoped_artifacts: ScopedArtifactRepository,
    ) -> None:
        self.courses = courses
        self.lessons = lessons
        self.resources = resources
        self.lesson_progress = lesson_progress
        self.scoped_artifacts = scoped_artifacts

    def list_lessons(self, *, course_id: int) -> dict[str, Any]:
        self._ensure_course(course_id)
        return {
            "items": [
                self._lesson_summary(course_id=course_id, lesson=lesson)
                for lesson in self.lessons.list_lessons(course_id)
            ]
        }

    def create_lesson(self, *, course_id: int, payload) -> dict[str, Any]:
        self._ensure_course(course_id)
        primary_video = None
        if payload.primary_video_resource_id is not None:
            primary_video = self._ensure_primary_video_resource(
                course_id=course_id,
                lesson_id=None,
                resource_id=payload.primary_video_resource_id,
            )
        self._ensure_primary_video_range(
            resource=primary_video,
            start_sec=payload.primary_video_start_sec,
            end_sec=payload.primary_video_end_sec,
            require_complete_range=primary_video is not None,
        )
        lesson = self.lessons.create_lesson(
            course_id=course_id,
            title=payload.title,
            source_type=payload.source_type,
            source_ref_json=payload.source_ref_json,
            primary_video_resource_id=payload.primary_video_resource_id,
            primary_video_start_sec=payload.primary_video_start_sec,
            primary_video_end_sec=payload.primary_video_end_sec,
        )
        return {"lesson": self._lesson_summary(course_id=course_id, lesson=lesson)}

    def get_lesson_detail(self, *, course_id: int, lesson_id: int) -> dict[str, Any]:
        self._ensure_course(course_id)
        lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        resources = self.resources.list_resources(course_id)
        lesson_resources = [
            resource
            for resource in resources
            if resource.get("scopeType") == "lesson" and resource.get("lessonId") == lesson_id
        ]
        primary_video = self._primary_video(lesson=lesson, resources=resources)
        artifact_summaries = self._lesson_artifact_summaries(course_id=course_id, lesson_id=lesson_id)
        progress = self._progress_summary(course_id=course_id, lesson_id=lesson_id)
        summary = self._lesson_summary(course_id=course_id, lesson=lesson, progress=progress)
        next_action = self._next_action(course_id=course_id, lesson=summary, primary_video=primary_video)
        return {
            "lesson": summary,
            "primaryVideo": primary_video,
            "lessonResources": lesson_resources,
            "artifactSummaries": artifact_summaries,
            "progress": progress,
            "citations": [],
            "sourceOverview": {
                "scopeType": "lesson",
                "lessonId": lesson_id,
                "resourceCount": len(lesson_resources),
                "primaryVideoResourceId": lesson.get("primaryVideoResourceId"),
                "hasPrimaryVideo": primary_video is not None,
                "lessonResourceCount": len(lesson_resources),
                "courseResourceCount": len([resource for resource in resources if resource.get("scopeType") == "course"]),
            },
            "knowledgePointPlaceholders": [
                {"type": "lesson_graph", "status": "placeholder", "items": []},
            ],
            "weaknessPlaceholders": [
                {"type": "lesson_review", "status": "placeholder", "items": []},
            ],
            "nextAction": next_action,
        }

    def update_lesson(self, *, course_id: int, lesson_id: int, payload) -> dict[str, Any]:
        self._ensure_course(course_id)
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        changes = payload.model_dump(exclude_none=True)
        if changes.get("lesson_status") == "deleted":
            raise ServiceError(
                message="Use the delete lesson endpoint to delete a lesson.",
                error_code="common.validation_error",
                status_code=400,
            )
        if not changes:
            lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
            return {"lesson": self._lesson_summary(course_id=course_id, lesson=lesson)}
        updated = self._update_lesson(course_id=course_id, lesson_id=lesson_id, changes=changes)
        return {"lesson": self._lesson_summary(course_id=course_id, lesson=updated)}

    def delete_lesson(self, *, course_id: int, lesson_id: int) -> dict[str, Any]:
        self._ensure_course(course_id)
        try:
            deleted = self.lessons.soft_delete_lesson(course_id=course_id, lesson_id=lesson_id)
        except ValueError as exc:
            raise self._service_error_from_value_error(exc) from exc
        return {"lesson": self._lesson_summary(course_id=course_id, lesson=deleted)}

    def reorder_lessons(self, *, course_id: int, payload) -> dict[str, Any]:
        self._ensure_course(course_id)
        try:
            lessons = self.lessons.reorder_lessons(course_id=course_id, lesson_ids=payload.lesson_ids)
        except ValueError as exc:
            raise self._service_error_from_value_error(exc) from exc
        return {
            "items": [
                self._lesson_summary(course_id=course_id, lesson=lesson)
                for lesson in lessons
            ]
        }

    def set_primary_video(self, *, course_id: int, lesson_id: int, payload) -> dict[str, Any]:
        self._ensure_course(course_id)
        self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        resource = self._ensure_primary_video_resource(
            course_id=course_id,
            lesson_id=lesson_id,
            resource_id=payload.resource_id,
        )
        self._ensure_primary_video_range(
            resource=resource,
            start_sec=payload.start_sec,
            end_sec=payload.end_sec,
            require_complete_range=False,
        )
        lesson = self._update_lesson(
            course_id=course_id,
            lesson_id=lesson_id,
            changes={
                "primary_video_resource_id": payload.resource_id,
                "primary_video_start_sec": payload.start_sec,
                "primary_video_end_sec": payload.end_sec,
            },
        )
        return {"lesson": self._lesson_summary(course_id=course_id, lesson=lesson)}

    def merge_lessons(self, *, course_id: int, payload) -> dict[str, Any]:
        self._ensure_course(course_id)
        target, stale_lessons = self._merge_targets(course_id=course_id, lesson_ids=payload.lesson_ids)
        title = payload.target_title or target["title"]
        target_lesson = self._update_lesson(
            course_id=course_id,
            lesson_id=int(target["lessonId"]),
            changes={"title": title},
        )
        self._move_lesson_resources(
            course_id=course_id,
            source_lesson_ids=[int(lesson["lessonId"]) for lesson in stale_lessons],
            target_lesson_id=int(target_lesson["lessonId"]),
        )
        stale_artifact_ids = self._mark_lesson_artifacts_stale(
            course_id=course_id,
            lesson_ids=[int(lesson["lessonId"]) for lesson in [target, *stale_lessons]],
        )
        for lesson in stale_lessons:
            try:
                self.lessons.soft_delete_lesson(course_id=course_id, lesson_id=int(lesson["lessonId"]))
            except ValueError as exc:
                raise self._service_error_from_value_error(exc) from exc
        target_lesson = self._ensure_lesson(course_id=course_id, lesson_id=int(target_lesson["lessonId"]))
        return {
            "lesson": self._lesson_summary(course_id=course_id, lesson=target_lesson),
            **self._stale_artifact_response(stale_artifact_ids),
        }

    def split_lesson(self, *, course_id: int, lesson_id: int, payload) -> dict[str, Any]:
        self._ensure_course(course_id)
        lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        original_video = self._ensure_primary_video_resource(
            course_id=course_id,
            lesson_id=lesson_id,
            resource_id=int(lesson["primaryVideoResourceId"]),
        ) if lesson.get("primaryVideoResourceId") is not None else None
        split_at = int(payload.split_at_sec)
        start_sec = int(lesson.get("primaryVideoStartSec") or 0)
        end_sec = self._split_end_sec(lesson=lesson)
        if lesson.get("primaryVideoResourceId") is None or split_at <= start_sec or split_at >= end_sec:
            raise ServiceError(
                message="Lesson split timestamp is outside the primary video range.",
                error_code="lesson.order_conflict",
                status_code=409,
            )
        if (original_video or {}).get("scopeType") == "lesson":
            self._update_resource_scope(
                course_id=course_id,
                resource_id=int(original_video["resourceId"]),
                scope_type="course",
                lesson_id=None,
                usage_role=original_video.get("usageRole") or "primary_video",
            )

        first_title = payload.first_title or lesson["title"]
        second_title = payload.second_title or f"{lesson['title']} 2"
        first_lesson = self._update_lesson(
            course_id=course_id,
            lesson_id=lesson_id,
            changes={
                "title": first_title,
                "primary_video_end_sec": split_at,
            },
        )
        second_lesson = self.lessons.create_lesson(
            course_id=course_id,
            title=second_title,
            source_type=lesson.get("sourceType") or "manual",
            source_ref_json=lesson.get("sourceRefJson"),
            primary_video_resource_id=lesson.get("primaryVideoResourceId"),
            primary_video_start_sec=split_at,
            primary_video_end_sec=end_sec,
        )
        self._place_split_lesson_after(
            course_id=course_id,
            first_lesson_id=int(first_lesson["lessonId"]),
            second_lesson_id=int(second_lesson["lessonId"]),
        )
        stale_artifact_ids = self._mark_lesson_artifacts_stale(course_id=course_id, lesson_ids=[lesson_id])
        first_lesson = self._ensure_lesson(course_id=course_id, lesson_id=lesson_id)
        second_lesson = self._ensure_lesson(course_id=course_id, lesson_id=int(second_lesson["lessonId"]))
        return {
            "firstLesson": self._lesson_summary(course_id=course_id, lesson=first_lesson),
            "secondLesson": self._lesson_summary(course_id=course_id, lesson=second_lesson),
            **self._stale_artifact_response(stale_artifact_ids),
        }

    def _ensure_course(self, course_id: int) -> dict[str, Any]:
        course = self.courses.get_course(course_id)
        if course is None:
            raise ServiceError(
                message="Course was not found.",
                error_code="course.not_found",
                status_code=404,
            )
        return course

    def _ensure_lesson(self, *, course_id: int, lesson_id: int) -> dict[str, Any]:
        lesson = self.lessons.get_lesson(course_id=course_id, lesson_id=lesson_id)
        if lesson is None:
            raise ServiceError(
                message="Lesson was not found.",
                error_code="lesson.not_found",
                status_code=404,
            )
        return lesson

    def _update_lesson(self, *, course_id: int, lesson_id: int, changes: dict[str, Any]) -> dict[str, Any]:
        updater = getattr(self.lessons, "update_lesson", None)
        if not callable(updater):
            raise ServiceError(
                message="Lesson updates are unavailable.",
                error_code="lesson.not_found",
                status_code=404,
            )
        try:
            lesson = updater(course_id=course_id, lesson_id=lesson_id, changes=changes)
        except ValueError as exc:
            raise self._service_error_from_value_error(exc) from exc
        if lesson is None:
            raise ServiceError(
                message="Lesson was not found.",
                error_code="lesson.not_found",
                status_code=404,
            )
        return lesson

    def _ensure_primary_video_resource(
        self,
        *,
        course_id: int,
        lesson_id: int | None,
        resource_id: int,
    ) -> dict[str, Any]:
        resource = self.resources.get_resource(resource_id)
        if resource is None or resource.get("courseId") != course_id:
            raise ServiceError(
                message="Resource was not found.",
                error_code="resource.not_found",
                status_code=404,
            )
        if resource.get("resourceType") not in VIDEO_RESOURCE_TYPES:
            raise ServiceError(
                message="Resource is not a playable video.",
                error_code="resource.not_video",
                status_code=409,
            )
        resource_lesson_id = resource.get("lessonId")
        if lesson_id is None and resource.get("scopeType") == "lesson":
            raise ServiceError(
                message="Lesson-scoped videos cannot be assigned before the lesson exists.",
                error_code="resource.lesson_mismatch",
                status_code=400,
            )
        if (
            lesson_id is not None
            and resource.get("scopeType") == "lesson"
            and resource_lesson_id is not None
            and resource_lesson_id != lesson_id
        ):
            raise ServiceError(
                message="Resource does not belong to this lesson.",
                error_code="resource.lesson_mismatch",
                status_code=400,
            )
        return resource

    def _ensure_primary_video_range(
        self,
        *,
        resource: dict[str, Any] | None,
        start_sec: int | None,
        end_sec: int | None,
        require_complete_range: bool,
    ) -> None:
        if resource is None and (start_sec is not None or end_sec is not None):
            raise ServiceError(
                message="Primary video range requires a primary video resource.",
                error_code="common.validation_error",
                status_code=400,
            )
        if require_complete_range and resource is not None and (start_sec is None or end_sec is None):
            raise ServiceError(
                message="Primary video range requires start and end seconds.",
                error_code="common.validation_error",
                status_code=400,
            )
        start = int(start_sec or 0)
        duration = int(resource["durationSec"]) if resource is not None and resource.get("durationSec") is not None else None
        if end_sec is not None and int(end_sec) <= start:
            raise ServiceError(
                message="Primary video range is invalid.",
                error_code="common.validation_error",
                status_code=400,
            )
        if duration is not None and start_sec is not None and start >= duration:
            raise ServiceError(
                message="Primary video range exceeds resource duration.",
                error_code="common.validation_error",
                status_code=400,
            )
        if duration is not None and end_sec is not None and int(end_sec) > duration:
            raise ServiceError(
                message="Primary video range exceeds resource duration.",
                error_code="common.validation_error",
                status_code=400,
            )

    def _move_lesson_resources(
        self,
        *,
        course_id: int,
        source_lesson_ids: Sequence[int],
        target_lesson_id: int,
    ) -> None:
        source_ids = {int(lesson_id) for lesson_id in source_lesson_ids}
        if not source_ids:
            return
        for resource in self.resources.list_resources(course_id):
            if resource.get("scopeType") != "lesson" or resource.get("lessonId") not in source_ids:
                continue
            self._update_resource_scope(
                course_id=course_id,
                resource_id=int(resource["resourceId"]),
                scope_type="lesson",
                lesson_id=target_lesson_id,
                usage_role=resource.get("usageRole"),
            )

    def _update_resource_scope(
        self,
        *,
        course_id: int,
        resource_id: int,
        scope_type: str,
        lesson_id: int | None,
        usage_role: str | None,
    ) -> dict[str, Any]:
        try:
            updated = self.resources.update_resource_scope(
                course_id=course_id,
                resource_id=resource_id,
                scope_type=scope_type,
                lesson_id=lesson_id,
                usage_role=usage_role,
            )
        except ValueError as exc:
            raise self._service_error_from_value_error(exc) from exc
        if updated is None:
            raise ServiceError(
                message="Resource was not found.",
                error_code="resource.not_found",
                status_code=404,
            )
        return updated

    def _lesson_summary(
        self,
        *,
        course_id: int,
        lesson: dict[str, Any],
        progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        progress = progress or self._progress_summary(course_id=course_id, lesson_id=int(lesson["lessonId"]))
        summary = dict(lesson)
        for key in (
            "lastPositionSec",
            "lastHandoutBlockId",
            "handoutReadPercent",
            "quizStatus",
            "reviewStatus",
            "lastActivityAt",
        ):
            if key in progress and progress[key] is not None:
                summary[key] = progress[key]
        summary["nextAction"] = summary.get("nextAction") or self._next_action(
            course_id=course_id,
            lesson=summary,
            primary_video={"resourceId": lesson.get("primaryVideoResourceId")}
            if lesson.get("primaryVideoResourceId") is not None
            else None,
        )
        return summary

    def _progress_summary(self, *, course_id: int, lesson_id: int) -> dict[str, Any]:
        progress = self.lesson_progress.get_user_lesson_progress(course_id=course_id, lesson_id=lesson_id)
        if progress is None:
            return {
                "lastPositionSec": None,
                "lastHandoutBlockId": None,
                "handoutReadPercent": 0,
                "quizStatus": "not_generated",
                "reviewStatus": "not_due",
                "lastActivityAt": None,
            }
        return {
            "lastPositionSec": progress.get("lastPositionSec"),
            "lastHandoutBlockId": progress.get("lastHandoutBlockId"),
            "handoutReadPercent": progress.get("handoutReadPercent", 0),
            "quizStatus": progress.get("quizStatus", "not_generated"),
            "reviewStatus": progress.get("reviewStatus", "not_due"),
            "lastActivityAt": progress.get("lastActivityAt"),
        }

    def _primary_video(
        self,
        *,
        lesson: dict[str, Any],
        resources: Sequence[dict[str, Any]],
    ) -> dict[str, Any] | None:
        resource_id = lesson.get("primaryVideoResourceId")
        if resource_id is None:
            return None
        for resource in resources:
            if resource.get("resourceId") == resource_id:
                return {
                    "resourceId": resource["resourceId"],
                    "resourceName": resource.get("originalName"),
                    "resourceType": resource.get("resourceType"),
                    "mimeType": resource.get("mimeType"),
                    "durationSec": resource.get("durationSec"),
                    "startSec": lesson.get("primaryVideoStartSec"),
                    "endSec": lesson.get("primaryVideoEndSec"),
                }
        return None

    def _lesson_artifact_summaries(self, *, course_id: int, lesson_id: int) -> list[dict[str, Any]]:
        lister = getattr(self.scoped_artifacts, "list_lesson_artifacts", None)
        if callable(lister):
            return lister(course_id=course_id, lesson_id=lesson_id)
        artifacts = getattr(self.scoped_artifacts, "scoped_artifacts", {})
        return [
            {
                "artifactId": artifact["artifactId"],
                "artifactType": artifact["artifactType"],
                "scopeType": artifact["scopeType"],
                "lessonId": artifact.get("lessonId"),
                "status": artifact["status"],
            }
            for artifact in sorted(artifacts.values(), key=lambda item: item["artifactId"])
            if artifact.get("courseId") == course_id
            and artifact.get("scopeType") == "lesson"
            and artifact.get("lessonId") == lesson_id
        ]

    def _mark_lesson_artifacts_stale(self, *, course_id: int, lesson_ids: Sequence[int]) -> list[dict[str, Any]]:
        marker = getattr(self.scoped_artifacts, "mark_lesson_artifacts_stale", None)
        if callable(marker):
            stale_artifacts = marker(course_id=course_id, lesson_ids=list(lesson_ids))
            if not stale_artifacts:
                return []
            if isinstance(stale_artifacts[0], dict):
                return list(stale_artifacts)
        return []

    def _stale_artifact_response(self, stale_artifacts: Sequence[dict[str, Any]]) -> dict[str, Any]:
        stale_artifact_ids: list[str] = []
        for artifact in stale_artifacts:
            artifact_id = artifact.get("artifactId")
            artifact_type = artifact.get("artifactType")
            if artifact_id is None or not artifact_type:
                continue
            stale_artifact_ids.append(f"{artifact_type}:{artifact_id}")
        return {
            "staleArtifacts": list(stale_artifacts),
            "staleArtifactIds": stale_artifact_ids,
        }

    def _merge_targets(
        self,
        *,
        course_id: int,
        lesson_ids: Sequence[int],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        requested_ids = [int(lesson_id) for lesson_id in lesson_ids]
        if len(requested_ids) < 2 or len(set(requested_ids)) != len(requested_ids):
            raise ServiceError(
                message="Lessons must be adjacent and unique.",
                error_code="lesson.order_conflict",
                status_code=409,
            )
        active_lessons = self.lessons.list_lessons(course_id)
        lesson_by_id = {int(lesson["lessonId"]): lesson for lesson in active_lessons}
        if any(lesson_id not in lesson_by_id for lesson_id in requested_ids):
            raise ServiceError(
                message="Lessons must belong to this course.",
                error_code="lesson.order_conflict",
                status_code=409,
            )
        active_ids = [int(lesson["lessonId"]) for lesson in active_lessons]
        try:
            positions = [active_ids.index(lesson_id) for lesson_id in requested_ids]
        except ValueError as exc:
            raise ServiceError(
                message="Lessons must belong to this course.",
                error_code="lesson.order_conflict",
                status_code=409,
            ) from exc
        if positions != list(range(positions[0], positions[0] + len(positions))):
            raise ServiceError(
                message="Lessons must be adjacent in course order.",
                error_code="lesson.order_conflict",
                status_code=409,
            )
        target = lesson_by_id[requested_ids[0]]
        stale_lessons = [lesson_by_id[lesson_id] for lesson_id in requested_ids[1:]]
        return target, stale_lessons

    def _place_split_lesson_after(
        self,
        *,
        course_id: int,
        first_lesson_id: int,
        second_lesson_id: int,
    ) -> None:
        active_ids = [int(lesson["lessonId"]) for lesson in self.lessons.list_lessons(course_id)]
        active_ids = [lesson_id for lesson_id in active_ids if lesson_id != second_lesson_id]
        try:
            insert_at = active_ids.index(first_lesson_id) + 1
        except ValueError as exc:
            raise ServiceError(
                message="Lesson order is invalid.",
                error_code="lesson.order_conflict",
                status_code=409,
            ) from exc
        ordered_ids = [*active_ids[:insert_at], second_lesson_id, *active_ids[insert_at:]]
        try:
            self.lessons.reorder_lessons(course_id=course_id, lesson_ids=ordered_ids)
        except ValueError as exc:
            raise self._service_error_from_value_error(exc) from exc

    def _split_end_sec(self, *, lesson: dict[str, Any]) -> int:
        end_sec = lesson.get("primaryVideoEndSec")
        if end_sec is not None:
            return int(end_sec)
        resource_id = lesson.get("primaryVideoResourceId")
        if resource_id is None:
            return 0
        resource = self.resources.get_resource(int(resource_id))
        return int(resource.get("durationSec") or 0) if resource is not None else 0

    def _next_action(
        self,
        *,
        course_id: int,
        lesson: dict[str, Any],
        primary_video: dict[str, Any] | None,
    ) -> dict[str, Any]:
        action_type = "continue_video" if primary_video is not None else "open_lesson"
        label = "继续本课时视频" if primary_video is not None else "打开本课时"
        return {
            "type": action_type,
            "label": label,
            "route": f"/courses/{course_id}/lessons/{lesson['lessonId']}",
        }

    def _service_error_from_value_error(self, exc: ValueError) -> ServiceError:
        error_code = str(exc) or "common.validation_error"
        status_code = {
            "course.not_found": 404,
            "lesson.not_found": 404,
            "lesson.order_conflict": 409,
            "resource.not_found": 404,
            "resource.not_video": 409,
            "resource.lesson_mismatch": 400,
            "resource.scope_required": 400,
            "artifact.scope_invalid": 400,
        }.get(error_code, 400)
        return ServiceError(
            message=error_code.replace(".", " "),
            error_code=error_code,
            status_code=status_code,
        )
