from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sqlalchemy import text

from app.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401 — register models with metadata


def _normalize_database_url(url: str) -> tuple[str, dict]:
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    connect_args: dict = {}

    if "sslmode" in query or "channel_binding" in query:
        sslmode = query.pop("sslmode", ["require"])[0]
        query.pop("channel_binding", None)
        if sslmode in {"require", "verify-ca", "verify-full"}:
            connect_args["ssl"] = True

    clean_query = urlencode({k: v[0] for k, v in query.items()})
    clean_url = urlunparse(parsed._replace(query=clean_query))
    return clean_url, connect_args


settings = get_settings()
_db_url, _connect_args = _normalize_database_url(settings.database_url)
engine = create_async_engine(
    _db_url,
    echo=settings.debug,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight dev migrations (create_all does not alter existing tables)
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS github_access_token TEXT"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE projects ADD COLUMN IF NOT EXISTS github_webhook_id INTEGER"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS last_commit_sha VARCHAR(64)"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS previous_commit_sha VARCHAR(64)"
            )
        )
