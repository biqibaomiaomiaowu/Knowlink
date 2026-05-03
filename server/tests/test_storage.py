from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from minio import Minio

from server.domain.services import ResourceService
from server.domain.services.errors import ServiceError
from server.domain.services.resources import UPLOAD_EXPIRES_IN
from server.infra.repositories.memory import MemoryScaffoldRepository
from server.infra.repositories.memory_runtime import RuntimeStore
from server.infra.storage import MinioObjectStorage, ObjectNotFoundError, ObjectStat, build_object_storage
from server.schemas.requests import UploadCompleteRequest, UploadInitRequest


class FakeObjectStorage:
    def __init__(self, stats: dict[str, ObjectStat] | None = None) -> None:
        self.stats = stats or {}
        self.presigned_calls: list[dict[str, object]] = []
        self.stat_calls: list[str] = []

    def presigned_put_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        self.presigned_calls.append(
            {
                "objectKey": object_key,
                "expires": expires,
                "contentType": content_type,
                "metadata": metadata,
            }
        )
        return f"https://storage.test/{object_key}?signature=fake"

    def stat_object(self, object_key: str) -> ObjectStat:
        self.stat_calls.append(object_key)
        try:
            return self.stats[object_key]
        except KeyError as exc:
            raise ObjectNotFoundError(object_key) from exc

    def read_object_bytes(self, object_key: str) -> bytes:
        self.stat_object(object_key)
        return b"fake"


class RecordingMinioClient:
    def __init__(self) -> None:
        self.presigned_call: tuple[str, str, timedelta] | None = None
        self.presigned_url_call: dict[str, object] | None = None
        self.metadata = {"x-amz-meta-sha256": "abc123"}

    def presigned_put_object(
        self,
        bucket_name: str,
        object_name: str,
        *,
        expires: timedelta,
    ) -> str:
        self.presigned_call = (bucket_name, object_name, expires)
        return "https://minio.test/knowlink/raw-object?X-Amz-Signature=fake"

    def get_presigned_url(
        self,
        method: str,
        bucket_name: str,
        object_name: str,
        *,
        expires: timedelta,
        extra_query_params: dict[str, str] | None = None,
    ) -> str:
        self.presigned_url_call = {
            "method": method,
            "bucketName": bucket_name,
            "objectName": object_name,
            "expires": expires,
            "extraQueryParams": extra_query_params,
        }
        return "https://minio.test/knowlink/raw-object?X-Amz-Signature=metadata"

    def stat_object(self, bucket_name: str, object_name: str):
        assert bucket_name == "knowlink"
        assert object_name == "raw/1/101/temp/pdf/demo.pdf"
        return SimpleNamespace(
            size=1024,
            etag="etag-demo",
            metadata=self.metadata,
        )


def _build_service(storage: FakeObjectStorage | None):
    repo = MemoryScaffoldRepository(RuntimeStore())
    course = repo.create_course(
        title="Object storage test course",
        entry_type="manual_import",
        goal_text="Verify MinIO upload slice",
        preferred_style="balanced",
    )
    service = ResourceService(
        courses=repo,
        resources=repo,
        idempotency=repo,
        storage=storage,
    )
    return service, repo, course["courseId"]


def _complete_payload(
    *,
    object_key: str,
    size_bytes: int = 1024,
    checksum: str = "sha256:abc123",
) -> UploadCompleteRequest:
    return UploadCompleteRequest(
        resource_type="pdf",
        object_key=object_key,
        original_name="demo.pdf",
        mime_type="application/pdf",
        size_bytes=size_bytes,
        checksum=checksum,
    )


def test_minio_storage_presigned_url_and_stat_are_passed_through():
    client = RecordingMinioClient()
    storage = MinioObjectStorage(client=client, bucket_name="knowlink")

    url = storage.presigned_put_url(
        "raw/1/101/temp/pdf/demo.pdf",
        expires=UPLOAD_EXPIRES_IN,
    )
    stat = storage.stat_object("raw/1/101/temp/pdf/demo.pdf")

    assert url == "https://minio.test/knowlink/raw-object?X-Amz-Signature=fake"
    assert client.presigned_call == (
        "knowlink",
        "raw/1/101/temp/pdf/demo.pdf",
        UPLOAD_EXPIRES_IN,
    )
    assert stat.size_bytes == 1024
    assert stat.checksum == "sha256:abc123"
    assert stat.etag == "etag-demo"


def test_minio_storage_presigned_url_signs_content_type_and_metadata():
    client = Minio(
        "minio.test",
        access_key="minio-access",
        secret_key="minio-secret",
        secure=True,
        region="us-east-1",
    )
    storage = MinioObjectStorage(client=client, bucket_name="knowlink")

    url = storage.presigned_put_url(
        "raw/1/101/temp/pdf/demo.pdf",
        expires=UPLOAD_EXPIRES_IN,
        content_type="application/pdf",
        metadata={
            "x-amz-meta-course-id": "101",
            "x-amz-meta-checksum": "sha256:abc123",
        },
    )

    query = parse_qs(urlsplit(url).query)
    assert query["X-Amz-SignedHeaders"] == [
        "content-type;host;x-amz-meta-checksum;x-amz-meta-course-id"
    ]
    assert "X-Amz-Signature" in query
    assert "Content-Type" not in query
    assert "x-amz-meta-course-id" not in query
    assert "x-amz-meta-checksum" not in query


def test_minio_storage_uses_public_endpoint_for_presign_and_internal_client_for_stat():
    internal_client = RecordingMinioClient()
    public_client = Minio(
        "127.0.0.1:9000",
        access_key="minio-access",
        secret_key="minio-secret",
        secure=False,
        region="us-east-1",
    )
    storage = MinioObjectStorage(
        client=internal_client,
        presign_client=public_client,
        bucket_name="knowlink",
    )

    url = storage.presigned_put_url(
        "raw/1/101/temp/pdf/demo.pdf",
        expires=UPLOAD_EXPIRES_IN,
        content_type="application/pdf",
        metadata={"x-amz-meta-course-id": "101"},
    )
    stat = storage.stat_object("raw/1/101/temp/pdf/demo.pdf")

    assert urlsplit(url).netloc == "127.0.0.1:9000"
    assert internal_client.presigned_call is None
    assert stat.size_bytes == 1024


def test_build_object_storage_uses_internal_endpoint_and_public_presign_endpoint():
    settings = SimpleNamespace(
        storage_backend="minio",
        minio_endpoint="legacy-minio:9000",
        minio_internal_endpoint="minio:9000",
        minio_public_endpoint="127.0.0.1:9000",
        minio_access_key="minio-access",
        minio_secret_key="minio-secret",
        minio_bucket="knowlink",
        minio_secure=False,
    )

    storage = build_object_storage(settings)

    assert isinstance(storage, MinioObjectStorage)
    assert storage.client._base_url._url.netloc == "minio:9000"
    assert storage.presign_client._base_url._url.netloc == "127.0.0.1:9000"
    url = storage.presigned_put_url(
        "raw/1/101/temp/pdf/demo.pdf",
        expires=UPLOAD_EXPIRES_IN,
        content_type="application/pdf",
        metadata={"x-amz-meta-course-id": "101"},
    )
    assert urlsplit(url).netloc == "127.0.0.1:9000"


def test_build_object_storage_falls_back_to_legacy_minio_endpoint():
    settings = SimpleNamespace(
        storage_backend="minio",
        minio_endpoint="legacy-minio:9000",
        minio_access_key="minio-access",
        minio_secret_key="minio-secret",
        minio_bucket="knowlink",
        minio_secure=False,
    )

    storage = build_object_storage(settings)

    assert isinstance(storage, MinioObjectStorage)
    assert storage.client._base_url._url.netloc == "legacy-minio:9000"
    assert storage.presign_client._base_url._url.netloc == "legacy-minio:9000"


def test_minio_storage_reads_full_checksum_metadata_from_stat():
    client = RecordingMinioClient()
    client.metadata = {"x-amz-meta-checksum": "sha256:def456"}
    storage = MinioObjectStorage(client=client, bucket_name="knowlink")

    stat = storage.stat_object("raw/1/101/temp/pdf/demo.pdf")

    assert stat.checksum == "sha256:def456"
    assert stat.metadata == {"x-amz-meta-checksum": "sha256:def456"}


def test_upload_init_uses_storage_presigned_url_and_course_scoped_key():
    storage = FakeObjectStorage()
    service, _, course_id = _build_service(storage)

    result = service.upload_init(
        course_id=course_id,
        request_host="api.test",
        payload=UploadInitRequest(
            resource_type="pdf",
            filename="../chapter 1.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            checksum="sha256:abc123",
        ),
    )

    assert result["uploadUrl"] == (
        f"https://storage.test/raw/1/{course_id}/temp/pdf/chapter_1.pdf?signature=fake"
    )
    assert result["objectKey"] == f"raw/1/{course_id}/temp/pdf/chapter_1.pdf"
    expected_headers = {
        "x-amz-meta-course-id": str(course_id),
        "x-amz-meta-checksum": "sha256:abc123",
        "x-amz-meta-sha256": "abc123",
    }
    assert result["headers"] == expected_headers
    assert storage.presigned_calls == [
        {
            "objectKey": f"raw/1/{course_id}/temp/pdf/chapter_1.pdf",
            "expires": UPLOAD_EXPIRES_IN,
            "contentType": "application/pdf",
            "metadata": expected_headers,
        }
    ]


def test_upload_complete_rejects_object_key_outside_course_prefix():
    storage = FakeObjectStorage()
    service, _, course_id = _build_service(storage)

    with pytest.raises(ServiceError) as exc_info:
        service.upload_complete(
            course_id=course_id,
            idempotency_key=None,
            payload=_complete_payload(object_key=f"raw/1/{course_id + 1}/temp/pdf/demo.pdf"),
        )

    assert exc_info.value.error_code == "storage.object_key_invalid"
    assert exc_info.value.status_code == 400
    assert storage.stat_calls == []


def test_upload_complete_fails_when_object_does_not_exist():
    storage = FakeObjectStorage()
    service, _, course_id = _build_service(storage)
    object_key = f"raw/1/{course_id}/temp/pdf/missing.pdf"

    with pytest.raises(ServiceError) as exc_info:
        service.upload_complete(
            course_id=course_id,
            idempotency_key=None,
            payload=_complete_payload(object_key=object_key),
        )

    assert exc_info.value.error_code == "storage.object_not_found"
    assert exc_info.value.status_code == 400
    assert storage.stat_calls == [object_key]


def test_upload_complete_rejects_checksum_from_object_metadata_mismatch():
    storage = FakeObjectStorage()
    service, _, course_id = _build_service(storage)
    object_key = f"raw/1/{course_id}/temp/pdf/demo.pdf"
    storage.stats[object_key] = ObjectStat(
        size_bytes=1024,
        checksum="sha256:deadbeef",
        metadata={"x-amz-meta-checksum": "sha256:deadbeef"},
    )

    with pytest.raises(ServiceError) as exc_info:
        service.upload_complete(
            course_id=course_id,
            idempotency_key=None,
            payload=_complete_payload(object_key=object_key),
        )

    assert exc_info.value.error_code == "storage.object_checksum_mismatch"
    assert exc_info.value.status_code == 409
    assert storage.stat_calls == [object_key]


def test_upload_complete_rejects_missing_checksum_from_object_stat():
    storage = FakeObjectStorage()
    service, _, course_id = _build_service(storage)
    object_key = f"raw/1/{course_id}/temp/pdf/demo.pdf"
    storage.stats[object_key] = ObjectStat(size_bytes=1024, checksum=None)

    with pytest.raises(ServiceError) as exc_info:
        service.upload_complete(
            course_id=course_id,
            idempotency_key=None,
            payload=_complete_payload(object_key=object_key),
        )

    assert exc_info.value.error_code == "storage.object_checksum_mismatch"
    assert exc_info.value.status_code == 409
    assert storage.stat_calls == [object_key]


def test_upload_complete_rejects_missing_payload_checksum_in_required_storage_mode():
    storage = FakeObjectStorage()
    service, _, course_id = _build_service(storage)
    object_key = f"raw/1/{course_id}/temp/pdf/demo.pdf"
    storage.stats[object_key] = ObjectStat(
        size_bytes=1024,
        checksum="sha256:abc123",
        metadata={"x-amz-meta-checksum": "sha256:abc123"},
    )

    with pytest.raises(ServiceError) as exc_info:
        service.upload_complete(
            course_id=course_id,
            idempotency_key=None,
            payload=_complete_payload(object_key=object_key, checksum=" "),
        )

    assert exc_info.value.error_code == "storage.object_checksum_mismatch"
    assert exc_info.value.status_code == 409
    assert storage.stat_calls == [object_key]


def test_upload_init_fails_when_storage_is_not_configured():
    service, _, course_id = _build_service(None)

    with pytest.raises(ServiceError) as exc_info:
        service.upload_init(
            course_id=course_id,
            request_host="api.test",
            payload=UploadInitRequest(
                resource_type="pdf",
                filename="demo.pdf",
                mime_type="application/pdf",
                size_bytes=1024,
                checksum="sha256:abc123",
            ),
        )

    assert exc_info.value.error_code == "storage.unavailable"
    assert exc_info.value.status_code == 503


def test_upload_complete_with_fake_storage_creates_resource():
    storage = FakeObjectStorage()
    service, repo, course_id = _build_service(storage)
    object_key = f"raw/1/{course_id}/temp/pdf/demo.pdf"
    storage.stats[object_key] = ObjectStat(
        size_bytes=1024,
        checksum="sha256:abc123",
        etag="etag-demo",
    )

    result = service.upload_complete(
        course_id=course_id,
        idempotency_key="storage-success-1",
        payload=_complete_payload(object_key=object_key),
    )

    assert result["resourceType"] == "pdf"
    assert result["objectKey"] == object_key
    assert result["ingestStatus"] == "ready"
    assert repo.list_resources(course_id) == [result]
