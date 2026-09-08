from unittest.mock import AsyncMock, patch

import pytest

from app.services.changes import get_project_changes
from app.models import Project, User


def _user() -> User:
    return User(
        id="u1",
        email="a@b.com",
        full_name="Test",
        github_access_token="gh-token",
        is_verified=True,
    )


def _project() -> Project:
    return Project(
        id="p1",
        user_id="u1",
        repo_full_name="acme/api",
        repo_url="https://github.com/acme/api",
        default_branch="main",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_get_project_changes_merges_prs_and_commits() -> None:
    user = _user()
    project = _project()

    with (
        patch(
            "app.services.changes.list_pull_requests",
            new_callable=AsyncMock,
            return_value=[
                {
                    "id": 1,
                    "type": "pr",
                    "title": "feat: x",
                    "author": "dev",
                    "branch": "feat",
                    "status": "open",
                    "merged": False,
                    "additions": 10,
                    "deletions": 2,
                    "timestamp": "2026-08-31T12:00:00Z",
                    "time": "1h ago",
                }
            ],
        ),
        patch(
            "app.services.changes.list_commits",
            new_callable=AsyncMock,
            return_value=[
                {
                    "id": "abc",
                    "type": "commit",
                    "title": "fix: y",
                    "author": "dev",
                    "branch": "main",
                    "status": "committed",
                    "additions": 0,
                    "deletions": 0,
                    "timestamp": "2026-08-31T10:00:00Z",
                    "time": "3h ago",
                }
            ],
        ),
    ):
        data = await get_project_changes(user, project)

    assert len(data["changes"]) == 2
    assert data["stats"]["open_prs"] == 1
