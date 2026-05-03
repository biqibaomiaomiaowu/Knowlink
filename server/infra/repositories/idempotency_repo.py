from typing import Callable, TypeVar
from server.domain.repositories.interfaces import IdempotencyRepository

T = TypeVar("T")

class IdempotencyRepository(IdempotencyRepository):
    async def run_idempotent(
        self, action: str, key: str | None, factory: Callable[[], T]
    ) -> T:
        return factory()