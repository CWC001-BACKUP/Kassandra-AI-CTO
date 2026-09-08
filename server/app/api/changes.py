from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.changes import ChangesResponse
from app.services.changes import get_project_changes
from app.services.github import GitHubError
from app.services.projects import get_active_project, get_user_project

router = APIRouter(tags=["changes"])


@router.get("/changes", response_model=ChangesResponse)
async def list_changes(
    project_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangesResponse:
    if project_id:
        project = await get_user_project(db, current_user.id, project_id)
    else:
        project = await get_active_project(db, current_user.id)

    if not project:
        return ChangesResponse(
            changes=[],
            stats={"this_week": 0, "open_prs": 0, "total_additions": 0, "total_deletions": 0},
            repo_full_name=None,
        )

    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")

    try:
        data = await get_project_changes(current_user, project)
    except GitHubError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return ChangesResponse(**data)
