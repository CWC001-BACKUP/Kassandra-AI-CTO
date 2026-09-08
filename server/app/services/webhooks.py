"""Process incoming GitHub webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from app.services.activity import log_activity
from app.services.memory import get_memory_provider

logger = logging.getLogger(__name__)


def verify_github_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not secret:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def find_project_by_repo(db: AsyncSession, full_name: str) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.repo_full_name == full_name)
    )
    return result.scalar_one_or_none()


async def handle_github_webhook(
    db: AsyncSession,
    event: str,
    payload: dict,
) -> dict:
    repo = payload.get("repository", {})
    full_name = repo.get("full_name")
    if not full_name:
        return {"handled": False, "reason": "no repository"}

    project = await find_project_by_repo(db, full_name)
    if not project:
        return {"handled": False, "reason": "project not tracked"}

    memory = get_memory_provider(full_name)

    if event == "push":
        ref = payload.get("ref", "")
        branch = ref.split("/")[-1] if ref else "unknown"
        commits = payload.get("commits", [])
        pusher = payload.get("pusher", {}).get("name", "unknown")

        for commit in commits[:5]:
            message = commit.get("message", "").split("\n")[0]
            await log_activity(
                db,
                user_id=project.user_id,
                project_id=project.id,
                source="webhook",
                message=f"Push to {branch}: {message}",
                metadata={"sha": commit.get("id"), "author": commit.get("author", {}).get("name")},
            )
            memory.save_context(
                inputs={"event": "push", "branch": branch, "author": pusher},
                outputs={"commit": message, "sha": commit.get("id")},
            )

        return {"handled": True, "event": "push", "commits": len(commits)}

    if event == "pull_request":
        pr = payload.get("pull_request", {})
        action = payload.get("action", "unknown")
        title = pr.get("title", "")
        number = pr.get("number")
        author = pr.get("user", {}).get("login", "unknown")

        await log_activity(
            db,
            user_id=project.user_id,
            project_id=project.id,
            source="webhook",
            message=f"PR #{number} {action}: {title}",
            metadata={"pr_number": number, "action": action},
        )
        memory.save_context(
            inputs={"event": "pull_request", "action": action, "pr": number},
            outputs={"title": title, "author": author},
        )
        return {"handled": True, "event": "pull_request", "action": action}

    return {"handled": False, "reason": f"unsupported event: {event}"}
