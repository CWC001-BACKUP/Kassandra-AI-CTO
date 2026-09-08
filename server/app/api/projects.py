from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.activity import AnalysisResponse
from app.schemas.project import (
    CreateProjectRequest,
    GitHubRepoResponse,
    MemorySearchResponse,
    ProjectResponse,
)
from app.services.github import GitHubError, list_user_repos
from app.services.memory import get_memory_provider
from app.services.projects import (
    activate_project,
    add_project_from_repo,
    delete_project,
    get_active_project,
    get_user_project,
    list_user_projects,
)
from app.services.repo_analysis import analyze_project

router = APIRouter(tags=["projects"])


@router.get("/github/repos", response_model=list[GitHubRepoResponse])
async def github_repos(
    current_user: User = Depends(get_current_user),
) -> list[GitHubRepoResponse]:
    if not current_user.github_access_token:
        raise HTTPException(
            status_code=400,
            detail="GitHub not connected. Sign in with GitHub to list your repositories.",
        )
    try:
        repos = await list_user_repos(current_user.github_access_token)
    except GitHubError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return [GitHubRepoResponse(**r) for r in repos]


@router.get("/projects", response_model=list[ProjectResponse])
async def get_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    projects = await list_user_projects(db, current_user.id)
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: CreateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    try:
        project = await add_project_from_repo(db, current_user, body.repo_full_name)
        await analyze_project(db, current_user, project)
    except GitHubError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/analyze", response_model=AnalysisResponse)
async def analyze_project_endpoint(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    project = await get_user_project(db, current_user.id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        result = await analyze_project(db, current_user, project)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AnalysisResponse(**result)


@router.post("/projects/{project_id}/activate", response_model=ProjectResponse)
async def set_active_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    try:
        project = await activate_project(db, current_user.id, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectResponse.model_validate(project)


@router.delete("/projects/{project_id}", status_code=204)
async def remove_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_project(db, current_user.id, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/memory/search", response_model=MemorySearchResponse)
async def search_memory(
    q: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemorySearchResponse:
    project = await get_active_project(db, current_user.id)
    tenant_id = project.repo_full_name if project else "default"

    provider = get_memory_provider(tenant_id)
    raw = provider.search(q)
    results: list[dict] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                results.append(item)
            else:
                results.append({"content": str(item)})

    return MemorySearchResponse(
        query=q,
        tenant_id=tenant_id,
        results=results,
        count=len(results),
    )
