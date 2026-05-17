from __future__ import annotations

import time
from xml.sax.saxutils import escape

from minio import Minio
from minio.error import S3Error

from server.config.settings import get_settings

MINIO_CORS_METHODS = ("GET", "HEAD", "PUT")
MINIO_CORS_ALLOWED_HEADERS = ("Authorization", "Content-Type", "Range", "x-amz-*")
MINIO_CORS_EXPOSE_HEADERS = (
    "Accept-Ranges",
    "Content-Range",
    "Content-Length",
    "Content-Type",
    "ETag",
)


def main() -> None:
    settings = get_settings()
    client = Minio(
        settings.minio_internal_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    deadline = time.monotonic() + 60
    while True:
        try:
            if not client.bucket_exists(settings.minio_bucket):
                client.make_bucket(settings.minio_bucket)
            configure_bucket_cors(
                client,
                bucket_name=settings.minio_bucket,
                allowed_origins=settings.cors_allow_origins,
            )
            print(f"MinIO bucket ready: {settings.minio_bucket}")
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def configure_bucket_cors(client, *, bucket_name: str, allowed_origins: tuple[str, ...]) -> bool:
    cors_xml = build_bucket_cors_xml(allowed_origins)
    try:
        client._execute(
            "PUT",
            bucket_name=bucket_name,
            body=cors_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            query_params={"cors": ""},
        )
    except S3Error as exc:
        if exc.code != "NotImplemented":
            raise
        print(
            "MinIO server does not support bucket CORS configuration; "
            "continuing with server-level CORS settings."
        )
        return False
    return True


def build_bucket_cors_xml(allowed_origins: tuple[str, ...]) -> str:
    rules = ["<CORSConfiguration>", "<CORSRule>"]
    for origin in allowed_origins:
        rules.append(f"<AllowedOrigin>{escape(origin)}</AllowedOrigin>")
    for method in MINIO_CORS_METHODS:
        rules.append(f"<AllowedMethod>{method}</AllowedMethod>")
    for header in MINIO_CORS_ALLOWED_HEADERS:
        rules.append(f"<AllowedHeader>{escape(header)}</AllowedHeader>")
    for header in MINIO_CORS_EXPOSE_HEADERS:
        rules.append(f"<ExposeHeader>{escape(header)}</ExposeHeader>")
    rules.append("<MaxAgeSeconds>3600</MaxAgeSeconds>")
    rules.append("</CORSRule>")
    rules.append("</CORSConfiguration>")
    return "".join(rules)


if __name__ == "__main__":
    main()
