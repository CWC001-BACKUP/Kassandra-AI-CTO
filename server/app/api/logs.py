from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.activity import ActivityLogResponse
from app.services.activity import list_activity_logs, log_to_dict

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[ActivityLogResponse])
async def get_logs(
    level: str = Query("all"),
    search: str | None = None,
    limit: int = Query(100, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityLogResponse]:
    entries = await list_activity_logs(
        db, current_user.id, level=level, search=search, limit=limit
    )
    return [ActivityLogResponse(**log_to_dict(e)) for e in entries]
