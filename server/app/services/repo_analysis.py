"""Automatic repository analysis via GitHub API — seeds Sibyl institutional memory."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Project, User
from app.services.activity import log_activity
from app.services.commit_cache import preload_recent_commits
from app.services.github import (
    create_repo_webhook,
    get_file_content,
    get_readme,
    get_repo,
    get_repo_languages,
    list_root_files,
)
from app.services.history_bootstrap import collect_history_signals, run_bootstrap_ingestion
from app.services.memory import get_memory_provider

logger = logging.getLogger(__name__)

KEY_FILES = (
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
)


async def analyze_project(
    db: AsyncSession,
    user: User,
    project: Project,
) -> dict:
    """Analyze a repo through the GitHub API and store findings in Sibyl memory.

    Bootstrap principle: reconstruct from the repository before interviewing the developer.
    """
    if not user.github_access_token:
        raise ValueError("GitHub not connected")

    token = user.github_access_token
    repo_name = project.repo_full_name

    await log_activity(
        db,
        user_id=user.id,
        project_id=project.id,
        source="analysis",
        message=f"Starting institutional memory bootstrap for {repo_name}",
    )

    repo = await get_repo(token, repo_name)
    languages = await get_repo_languages(token, repo_name)
    readme = await get_readme(token, repo_name)
    root_files = await list_root_files(token, repo_name)

    config_snippets: dict[str, str] = {}
    for filename in KEY_FILES:
        if filename in root_files:
            content = await get_file_content(token, repo_name, filename)
            if content:
                config_snippets[filename] = content

    memory = get_memory_provider(repo_name)

    # Legacy overview entity (kept for existing chat/search paths)
    memory.remember(
        "architecture",
        "overview",
        {
            "repo": repo_name,
            "description": repo.get("description"),
            "default_branch": repo.get("default_branch"),
            "primary_language": repo.get("language"),
            "languages": languages,
            "root_files": root_files[:40],
        },
    )

    if readme:
        memory.set_reference("readme", readme[:12000])

    for filename, content in config_snippets.items():
        # Never store env-like secrets; skip obvious secret filenames
        if filename.lower() in {".env", ".env.local", "credentials.json"}:
            continue
        memory.set_reference(filename, content[:8000])

    branch = repo.get("default_branch") or project.default_branch or "main"
    try:
        await preload_recent_commits(token, repo_name, branch=branch)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Commit preload failed for %s: %s", repo_name, exc)

    history_memories, inferred_memories, history_meta = await collect_history_signals(
        token,
        repo_name,
        branch=branch,
        project_id=project.id,
    )

    understanding = run_bootstrap_ingestion(
        tenant_id=repo_name,
        project_id=project.id,
        repo_full_name=repo_name,
        languages=languages,
        root_files=root_files,
        config_snippets=config_snippets,
        readme=readme,
        history_memories=history_memories,
        inferred_memories=inferred_memories,
        history_meta=history_meta,
    )

    counts = understanding.get("counts") or {}
    memory.save_context(
        inputs={"event": "repo_analysis", "repo": repo_name, "phase": "bootstrap"},
        outputs={
            "summary": (
                f"Bootstrapped institutional memory for {repo_name}: "
                f"{counts.get('observed', 0)} observed, "
                f"{counts.get('inferred', 0)} inferred, "
                f"{counts.get('knowledge_gaps', 0)} knowledge gaps."
            ),
            "config_files": list(config_snippets.keys()),
            "history_meta": history_meta,
        },
    )

    project.description = repo.get("description") or project.description
    project.default_branch = repo.get("default_branch", project.default_branch)
    project.language = repo.get("language") or project.language
    project.analyzed_at = datetime.now(UTC)

    settings = get_settings()
    if settings.webhook_base_url and settings.github_webhook_secret and not project.github_webhook_id:
        webhook_url = f"{settings.webhook_base_url.rstrip('/')}/webhooks/github"
        hook_id = await create_repo_webhook(
            token,
            repo_name,
            webhook_url,
            settings.github_webhook_secret,
        )
        if hook_id:
            project.github_webhook_id = hook_id
            await log_activity(
                db,
                user_id=user.id,
                project_id=project.id,
                source="webhook",
                message=f"GitHub webhook registered for {repo_name}",
                metadata={"webhook_id": hook_id},
            )

    await log_activity(
        db,
        user_id=user.id,
        project_id=project.id,
        source="analysis",
        message=f"Institutional memory bootstrap completed for {repo_name}",
        metadata={
            "languages": list(languages.keys()),
            "config_files": list(config_snippets.keys()),
            "observed": counts.get("observed"),
            "inferred": counts.get("inferred"),
            "knowledge_gaps": counts.get("knowledge_gaps"),
        },
    )

    return {
        "repo_full_name": repo_name,
        "analyzed_at": project.analyzed_at.isoformat(),
        "languages": languages,
        "root_files": root_files,
        "config_files": list(config_snippets.keys()),
        "readme_found": bool(readme),
        "webhook_registered": project.github_webhook_id is not None,
        "understanding": understanding,
        "counts": counts,
        "history_meta": history_meta,
    }
