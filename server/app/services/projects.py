from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.services.github import GitHubError, get_repo


async def list_user_projects(db: AsyncSession, user_id: str) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.is_active.desc(), Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_user_project(db: AsyncSession, user_id: str, project_id: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_active_project(db: AsyncSession, user_id: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.user_id == user_id, Project.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def add_project_from_repo(
    db: AsyncSession,
    user: User,
    repo_full_name: str,
) -> Project:
    if not user.github_access_token:
        raise GitHubError(
            "GitHub is not connected. Sign in with GitHub or re-authorize to list repos.",
            400,
        )

    repo = await get_repo(user.github_access_token, repo_full_name.strip())

    existing = await db.execute(
        select(Project).where(
            Project.user_id == user.id,
            Project.repo_full_name == repo["full_name"],
        )
    )
    project = existing.scalar_one_or_none()
    if project:
        project.description = repo.get("description")
        project.default_branch = repo.get("default_branch", "main")
        project.language = repo.get("language")
        await _set_active_project(db, user.id, project)
        return project

    result = await db.execute(select(Project).where(Project.user_id == user.id))
    has_any = result.scalars().first() is not None

    project = Project(
        user_id=user.id,
        repo_full_name=repo["full_name"],
        repo_url=repo["html_url"],
        description=repo.get("description"),
        default_branch=repo.get("default_branch", "main"),
        language=repo.get("language"),
        is_active=not has_any,
    )
    db.add(project)
    await db.flush()
    return project


async def _set_active_project(db: AsyncSession, user_id: str, active: Project) -> None:
    result = await db.execute(select(Project).where(Project.user_id == user_id))
    for project in result.scalars().all():
        project.is_active = project.id == active.id


async def activate_project(db: AsyncSession, user_id: str, project_id: str) -> Project:
    project = await get_user_project(db, user_id, project_id)
    if not project:
        raise ValueError("Project not found")
    await _set_active_project(db, user_id, project)
    return project


async def delete_project(db: AsyncSession, user_id: str, project_id: str) -> None:
    project = await get_user_project(db, user_id, project_id)
    if not project:
        raise ValueError("Project not found")
    was_active = project.is_active
    await db.delete(project)
    await db.flush()

    if was_active:
        result = await db.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
        )
        next_project = result.scalars().first()
        if next_project:
            next_project.is_active = True
