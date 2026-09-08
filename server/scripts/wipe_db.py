#!/usr/bin/env python3
"""Wipe the Kassandra PostgreSQL database and recreate an empty schema.

Also optionally clears local Sibyl SQLite memory files.

Uses DATABASE_URL from server/.env (see .env.example).

Run from server/:
    python -m scripts.wipe_db --yes
    python -m scripts.wipe_db --yes --sibyl
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from app.config import get_settings
from app.db.session import engine, init_db
from app.db.base import Base
import app.models  # noqa: F401 — register models with metadata


def _redact_database_url(url: str) -> str:
    """Hide credentials while showing host and database name."""
    parsed = urlparse(url.replace("postgresql+asyncpg://", "postgresql://"))
    host = parsed.hostname or "unknown-host"
    port = f":{parsed.port}" if parsed.port else ""
    database = (parsed.path or "/").lstrip("/") or "unknown-db"
    user = parsed.username or "user"
    return f"postgresql://{user}:***@{host}{port}/{database}"


def _wipe_sibyl_files(data_dir: Path) -> int:
    if not data_dir.exists():
        return 0

    removed = 0
    for path in data_dir.glob("*.db"):
        path.unlink(missing_ok=True)
        removed += 1
        wal = path.with_suffix(path.suffix + "-wal")
        shm = path.with_suffix(path.suffix + "-shm")
        wal.unlink(missing_ok=True)
        shm.unlink(missing_ok=True)

    from app.services import memory as memory_module

    memory_module._provider_cache.clear()
    return removed


async def wipe_postgres() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()


async def run(*, include_sibyl: bool) -> int:
    settings = get_settings()
    db_label = _redact_database_url(settings.database_url)

    print("=" * 72)
    print("KASSANDRA DATABASE WIPE")
    print("=" * 72)
    print(f"PostgreSQL: {db_label}")
    print("Action:     DROP all tables, recreate empty schema")
    if include_sibyl:
        print(f"Sibyl:      delete *.db under {settings.sibyl_data_dir}")
    print()

    await wipe_postgres()
    print("[OK] PostgreSQL wiped and schema recreated.")

    if include_sibyl:
        data_dir = Path(settings.sibyl_data_dir).expanduser().resolve()
        count = _wipe_sibyl_files(data_dir)
        print(f"[OK] Removed {count} Sibyl SQLite file(s) from {data_dir}.")

    print()
    print("Done. All users, projects, chat sessions, and tokens are gone.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wipe Kassandra PostgreSQL data and recreate an empty schema."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive wipe (required).",
    )
    parser.add_argument(
        "--sibyl",
        action="store_true",
        help="Also delete local Sibyl SQLite memory files (SIBYL_DATA_DIR).",
    )
    args = parser.parse_args()

    if not args.yes:
        settings = get_settings()
        print("This will permanently delete all application data.")
        print(f"Target: {_redact_database_url(settings.database_url)}")
        print()
        print("Re-run with --yes to confirm:")
        print("  python -m scripts.wipe_db --yes")
        raise SystemExit(1)

    raise SystemExit(asyncio.run(run(include_sibyl=args.sibyl)))


if __name__ == "__main__":
    main()
