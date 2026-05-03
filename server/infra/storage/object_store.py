from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol
from urllib.parse import SplitResult, urlunsplit

from minio import Minio, time
from minio.error import S3Error
from minio.helpers import check_bucket_name, check_object_name, queryencode
from minio.signer import (
    _get_canonical_headers,
    _get_canonical_query_string,
    _get_scope,
    _get_signature,
    _get_signing_key,
    _get_string_to_sign,
    sha256_hash,
)


class ObjectStorageError(Exception):
    """Base error for storage adapter failures."""


class ObjectNotFoundError(ObjectStorageError):
    """Raised when the requested object does not exist."""


class ObjectStorageUnavailable(ObjectStorageError):
    """Raised when object storage cannot serve the request."""


@dataclass(frozen=True)
class ObjectStat:
    size_bytes: int | None
    checksum: str | None = None
    etag: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    checksum_required: bool = True


class ObjectStorage(Protocol):
    def presigned_put_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> str: ...

    def stat_object(self, object_key: str) -> ObjectStat: ...

    def read_object_bytes(self, object_key: str) -> bytes: ...


class MinioObjectStorage:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        bucket_name: str = "knowlink",
        secure: bool = False,
        client: Minio | None = None,
        public_endpoint: str | None = None,
        presign_client: Minio | None = None,
    ) -> None:
        if client is None:
            if endpoint is None or access_key is None or secret_key is None:
                raise ValueError("endpoint, access_key and secret_key are required without client")
            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
        if presign_client is None and public_endpoint:
            if access_key is None or secret_key is None:
                raise ValueError("access_key and secret_key are required with public_endpoint")
            presign_client = Minio(
                public_endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
                region="us-east-1",
            )
        self.client = client
        self.presign_client = presign_client or client
        self.bucket_name = bucket_name

    def presigned_put_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> str:
        signed_headers = _presigned_put_headers(content_type=content_type, metadata=metadata)
        try:
            if signed_headers:
                return _get_presigned_url_with_headers(
                    client=self.presign_client,
                    method="PUT",
                    bucket_name=self.bucket_name,
                    object_name=object_key,
                    expires=expires,
                    headers=signed_headers,
                )
            return self.presign_client.presigned_put_object(
                self.bucket_name,
                object_key,
                expires=expires,
            )
        except Exception as exc:  # pragma: no cover - covered via service mapping.
            raise ObjectStorageUnavailable("Failed to generate presigned upload URL") from exc

    def stat_object(self, object_key: str) -> ObjectStat:
        try:
            value = self.client.stat_object(self.bucket_name, object_key)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                raise ObjectNotFoundError(object_key) from exc
            raise ObjectStorageUnavailable("Failed to stat object") from exc
        except Exception as exc:  # pragma: no cover - defensive adapter boundary.
            raise ObjectStorageUnavailable("Failed to stat object") from exc

        metadata = dict(getattr(value, "metadata", None) or {})
        return ObjectStat(
            size_bytes=getattr(value, "size", None),
            checksum=_checksum_from_metadata(metadata),
            etag=getattr(value, "etag", None),
            metadata=metadata,
        )

    def read_object_bytes(self, object_key: str) -> bytes:
        try:
            response = self.client.get_object(self.bucket_name, object_key)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject"}:
                raise ObjectNotFoundError(object_key) from exc
            raise ObjectStorageUnavailable("Failed to read object") from exc
        except Exception as exc:  # pragma: no cover - defensive adapter boundary.
            raise ObjectStorageUnavailable("Failed to read object") from exc

        try:
            return response.read()
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
            release_conn = getattr(response, "release_conn", None)
            if callable(release_conn):
                release_conn()


def _checksum_from_metadata(metadata: Mapping[str, str]) -> str | None:
    normalized = {key.lower(): value for key, value in metadata.items()}
    for key in (
        "x-amz-meta-checksum",
        "x-amz-meta-sha256",
        "checksum",
        "sha256",
    ):
        value = normalized.get(key)
        if not value:
            continue
        value = value.strip()
        if key.endswith("sha256") and not value.startswith("sha256:"):
            return f"sha256:{value}"
        return value
    return None


def _presigned_put_headers(
    *,
    content_type: str | None,
    metadata: Mapping[str, str] | None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if content_type:
        headers["content-type"] = content_type
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        headers[str(key).lower()] = str(value)
    return headers


def _get_presigned_url_with_headers(
    *,
    client: Minio,
    method: str,
    bucket_name: str,
    object_name: str,
    expires: timedelta,
    headers: Mapping[str, str],
) -> str:
    check_bucket_name(bucket_name, s3_check=client._base_url.is_aws_host)
    check_object_name(object_name)
    if expires.total_seconds() < 1 or expires.total_seconds() > 604800:
        raise ValueError("expires must be between 1 second to 7 days")

    region = client._get_region(bucket_name)
    query_params: dict[str, str] = {}
    credentials = client._provider.retrieve() if client._provider else None
    if credentials and credentials.session_token:
        query_params["X-Amz-Security-Token"] = credentials.session_token

    url = client._base_url.build(
        method=method,
        region=region,
        bucket_name=bucket_name,
        object_name=object_name,
        query_params=query_params,
    )

    if credentials:
        url = _presign_v4_with_headers(
            method=method,
            url=url,
            region=region,
            credentials=credentials,
            date=time.utcnow(),
            expires=int(expires.total_seconds()),
            headers={"host": url.netloc, **headers},
        )
    return urlunsplit(url)


def _presign_v4_with_headers(
    *,
    method: str,
    url: SplitResult,
    region: str,
    credentials,
    date,
    expires: int,
    headers: Mapping[str, str],
) -> SplitResult:
    scope = _get_scope(date, region, "s3")
    canonical_headers, signed_headers = _get_canonical_headers(headers)
    query = url.query + "&" if url.query else ""
    query += (
        "X-Amz-Algorithm=AWS4-HMAC-SHA256"
        f"&X-Amz-Credential={queryencode(credentials.access_key + '/' + scope)}"
        f"&X-Amz-Date={time.to_amz_date(date)}"
        f"&X-Amz-Expires={expires}"
        f"&X-Amz-SignedHeaders={queryencode(signed_headers)}"
    )
    parts = list(url)
    parts[3] = query
    signed_url = SplitResult(*parts)
    canonical_query_string = _get_canonical_query_string(query)
    canonical_request = (
        f"{method}\n"
        f"{signed_url.path or '/'}\n"
        f"{canonical_query_string}\n"
        f"{canonical_headers}\n\n"
        f"{signed_headers}\n"
        "UNSIGNED-PAYLOAD"
    )
    string_to_sign = _get_string_to_sign(date, scope, sha256_hash(canonical_request))
    signing_key = _get_signing_key(credentials.secret_key, date, region, "s3")
    signature = _get_signature(signing_key, string_to_sign)
    parts[3] = query + "&X-Amz-Signature=" + queryencode(signature)
    return SplitResult(*parts)


class DemoObjectStorage:
    def presigned_put_url(
        self,
        object_key: str,
        *,
        expires: timedelta,
        content_type: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> str:
        return f"http://object-storage.local/{object_key}?demo=1"

    def stat_object(self, object_key: str) -> ObjectStat:
        return ObjectStat(size_bytes=None, checksum_required=False)

    def read_object_bytes(self, object_key: str) -> bytes:
        return b""


def build_object_storage(settings) -> ObjectStorage | None:
    backend = settings.storage_backend.strip().lower()
    if backend in {"", "none", "disabled"}:
        return None
    if backend in {"demo", "fake", "memory", "local"}:
        return DemoObjectStorage()
    if backend == "minio":
        return MinioObjectStorage(
            endpoint=getattr(settings, "minio_internal_endpoint", None) or settings.minio_endpoint,
            public_endpoint=getattr(settings, "minio_public_endpoint", None) or None,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket_name=settings.minio_bucket,
            secure=settings.minio_secure,
        )
    raise RuntimeError(f"Unsupported KNOWLINK_STORAGE_BACKEND: {settings.storage_backend}")
