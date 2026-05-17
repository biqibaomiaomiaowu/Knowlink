from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import server.infra.db.models
from server.domain.services.errors import ServiceError
from server.domain.services.resources import ResourceService
from server.infra.db.base import Base
from server.infra.db.models import CourseResource, CourseSegment
from server.infra.repositories.sqlalchemy import SqlAlchemyRuntimeRepository


def test_sql_resource_deletion_rejects_resource_with_backend_artifacts():
    repo, session = _build_repository()
    course = repo.create_course(
        title="Deletion conflict course",
        entry_type="manual_import",
        goal_text="verify deletion semantics",
        preferred_style="balanced",
    )
    resource = repo.create_resource(course["courseId"], _resource_payload("lecture.pdf"))
    parse_run, _ = repo.create_parse_run(course["courseId"])
    session.add(
        CourseSegment(
            course_id=course["courseId"],
            resource_id=resource["resourceId"],
            parse_run_id=parse_run["parseRunId"],
            segment_type="pdf_page_text",
            text_content="dependent segment",
            plain_text="dependent segment",
            page_no=1,
            order_no=1,
            token_count=2,
            is_active=True,
        )
    )
    session.commit()

    service = ResourceService(courses=repo, resources=repo, idempotency=repo)
    try:
        service.delete_resource(course_id=course["courseId"], resource_id=resource["resourceId"])
    except ServiceError as exc:
        assert exc.status_code == 409
        assert exc.error_code == "resource.has_dependents"
    else:
        raise AssertionError("Expected dependent resource deletion to be rejected")

    assert session.get(CourseResource, resource["resourceId"]) is not None
    assert session.scalar(sa.select(sa.func.count()).select_from(CourseSegment)) == 1


def test_sql_resource_deletion_allows_unreferenced_resource():
    repo, session = _build_repository()
    course = repo.create_course(
        title="Deletion success course",
        entry_type="manual_import",
        goal_text="verify deletion success",
        preferred_style="balanced",
    )
    resource = repo.create_resource(course["courseId"], _resource_payload("loose.pdf"))

    service = ResourceService(courses=repo, resources=repo, idempotency=repo)
    result = service.delete_resource(course_id=course["courseId"], resource_id=resource["resourceId"])

    assert result == {"deleted": True, "resourceId": resource["resourceId"]}
    assert session.get(CourseResource, resource["resourceId"]) is None


def _build_repository() -> tuple[SqlAlchemyRuntimeRepository, sa.orm.Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()
    return SqlAlchemyRuntimeRepository(session), session


def _resource_payload(original_name: str) -> dict[str, object]:
    return {
        "resourceType": "pdf",
        "sourceType": "upload",
        "objectKey": f"raw/1/1/temp/pdf/{original_name}",
        "originalName": original_name,
        "mimeType": "application/pdf",
        "sizeBytes": 1024,
        "checksum": "sha256:abc123",
    }
