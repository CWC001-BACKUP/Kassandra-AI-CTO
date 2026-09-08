"""Persist and query activity logs."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActivityLog


async def log_activity(
    db: AsyncSession,
    *,
    message: str,
    level: str = "info",
    source: str = "system",
    user_id: str | None = None,
    project_id: str | None = None,
    metadata: dict | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        user_id=user_id,
        project_id=project_id,
        level=level,
        source=source,
        message=message,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_activity_logs(
    db: AsyncSession,
    user_id: str,
    *,
    level: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[ActivityLog]:
    query = select(ActivityLog).where(ActivityLog.user_id == user_id)

    if level and level != "all":
        query = query.where(ActivityLog.level == level)

    if search:
        query = query.where(ActivityLog.message.ilike(f"%{search}%"))

    query = query.order_by(desc(ActivityLog.created_at)).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


def log_to_dict(entry: ActivityLog) -> dict:
    metadata = None
    if entry.metadata_json:
        try:
            metadata = json.loads(entry.metadata_json)
        except json.JSONDecodeError:
            metadata = None

    created = entry.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)

    return {
        "id": entry.id,
        "level": entry.level,
        "source": entry.source,
        "message": entry.message,
        "project_id": entry.project_id,
        "metadata": metadata,
        "timestamp": created.isoformat(),
    }
