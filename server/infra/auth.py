from __future__ import annotations

from dataclasses import dataclass

from server.config.settings import Settings


@dataclass(frozen=True)
class DemoUser:
    user_id: int
    nickname: str


def authenticate_token(token: str | None, settings: Settings) -> DemoUser | None:
    if token != settings.demo_token:
        return None
    return DemoUser(user_id=settings.demo_user_id, nickname=settings.demo_user_name)
