from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from server.infra.db.session import create_session


def get_db() -> Generator[Session, None, None]:
    session = create_session()
    try:
        yield session
    finally:
        session.close()
