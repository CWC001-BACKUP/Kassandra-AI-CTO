"""Aggregate GitHub PRs and commits for the Changes view."""

from __future__ import annotations

from app.models import Project, User
from app.services.github import GitHubError, list_commits, list_pull_requests


async def get_project_changes(user: User, project: Project) -> dict:
    if not user.github_access_token:
        raise GitHubError("GitHub not connected", 400)

    prs = await list_pull_requests(
        user.github_access_token, project.repo_full_name, per_page=15
    )
    commits = await list_commits(
        user.github_access_token,
        project.repo_full_name,
        branch=project.default_branch,
        per_page=15,
    )

    # Mark merged PRs correctly
    for pr in prs:
        if pr.get("merged"):
            pr["status"] = "merged"

    changes = prs + commits
    changes.sort(key=lambda c: c.get("timestamp") or "", reverse=True)

    open_prs = sum(1 for c in prs if c["status"] == "open")
    this_week = len(changes)

    return {
        "changes": changes[:30],
        "stats": {
            "this_week": this_week,
            "open_prs": open_prs,
            "total_additions": sum(c.get("additions", 0) for c in changes),
            "total_deletions": sum(c.get("deletions", 0) for c in changes),
        },
        "repo_full_name": project.repo_full_name,
    }
