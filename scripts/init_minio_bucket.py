from __future__ import annotations

import time

from minio import Minio

from server.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    deadline = time.monotonic() + 60
    while True:
        try:
            if not client.bucket_exists(settings.minio_bucket):
                client.make_bucket(settings.minio_bucket)
            print(f"MinIO bucket ready: {settings.minio_bucket}")
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


if __name__ == "__main__":
    main()
