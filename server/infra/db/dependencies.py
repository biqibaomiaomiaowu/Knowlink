from server.infra.db.session import AsyncSessionLocal
from typing import AsyncGenerator

async def get_db() -> AsyncGenerator[AsyncSessionLocal, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()