from __future__ import annotations

from typing import Any

from server.domain.services.errors import ServiceError


class UnavailableBiliClient:
    def create_qr_session(self) -> dict[str, Any]:
        raise ServiceError(
            message="Bilibili client is not implemented yet.",
            error_code="bilibili.client_unavailable",
            status_code=503,
        )

    def refresh_qr_session(
        self,
        session_id: str,
        poll_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        raise ServiceError(
            message="Bilibili client is not implemented yet.",
            error_code="bilibili.client_unavailable",
            status_code=503,
        )

    def preview(self, source_url: str, cookies: dict[str, Any]) -> dict[str, Any]:
        raise ServiceError(
            message="Bilibili client is not implemented yet.",
            error_code="bilibili.client_unavailable",
            status_code=503,
        )
