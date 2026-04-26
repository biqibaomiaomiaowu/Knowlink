from __future__ import annotations


class ServiceError(Exception):
    def __init__(self, *, message: str, error_code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
