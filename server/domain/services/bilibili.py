from __future__ import annotations

from server.domain.services.errors import ServiceError


class BilibiliService:
    def create_import(
        self,
        *,
        course_id: int,
        video_url: str | None,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        raise self._not_implemented()

    def list_imports(self, *, course_id: int) -> dict[str, object]:
        raise self._not_implemented()

    def get_import_status(self, *, import_run_id: int) -> dict[str, object]:
        raise self._not_implemented()

    def cancel_import(
        self,
        *,
        import_run_id: int,
        idempotency_key: str | None,
    ) -> dict[str, object]:
        raise self._not_implemented()

    def create_qr_session(self) -> dict[str, object]:
        raise self._not_implemented()

    def get_qr_session(self, *, session_id: str) -> dict[str, object]:
        raise self._not_implemented()

    def get_auth_session(self) -> dict[str, object]:
        raise self._not_implemented()

    def delete_auth_session(self) -> dict[str, object]:
        raise self._not_implemented()

    @staticmethod
    def _not_implemented() -> ServiceError:
        return ServiceError(
            message="Bilibili import and auth contract is reserved but not implemented yet.",
            error_code="bilibili.not_implemented",
            status_code=501,
        )
