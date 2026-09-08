from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ActivityLog, Project, Report, User
from app.services.changes import get_project_changes
from app.services.memory import get_memory_provider
from app.services.projects import get_active_project, list_user_projects

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    projects = await list_user_projects(db, current_user.id)
    active = await get_active_project(db, current_user.id)

    memory_count = 0
    if active:
        try:
            hits = get_memory_provider(active.repo_full_name).search("")
            memory_count = len(hits) if isinstance(hits, list) else 0
        except Exception:  # noqa: BLE001
            memory_count = 0

    changes_today = 0
    if active and current_user.github_access_token:
        try:
            data = await get_project_changes(current_user, active)
            changes_today = data["stats"]["this_week"]
        except Exception:  # noqa: BLE001
            changes_today = 0

    report_count = await db.execute(
        select(func.count()).select_from(Report).where(Report.user_id == current_user.id)
    )

    return {
        "projects_count": len(projects),
        "active_project": active.repo_full_name if active else None,
        "memory_count": memory_count,
        "changes_today": changes_today,
        "reports_count": report_count.scalar() or 0,
    }


@router.get("/activity")
async def dashboard_activity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == current_user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(8)
    )
    items = []
    for entry in result.scalars().all():
        items.append(
            {
                "type": entry.source,
                "message": entry.message,
                "time": entry.created_at.isoformat() if entry.created_at else "",
            }
        )
    return items
