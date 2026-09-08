from unittest.mock import AsyncMock, patch

import pytest

from app.models import Project, User
from app.services.cross_repo import (
    is_cross_repo_question,
    is_single_repo_commit_scope,
    match_projects_in_message,
    process_cross_repo_message,
    resolve_cross_repo_projects,
)


def _make_user() -> User:
    return User(
        id="user-1",
        email="dev@example.com",
        full_name="Dev User",
        github_username="devuser",
        github_access_token="gh-token",
        is_verified=True,
    )


def _project(pid: str, name: str) -> Project:
    return Project(
        id=pid,
        user_id="user-1",
        repo_full_name=name,
        repo_url=f"https://github.com/{name}",
        default_branch="main",
        is_active=pid == "p1",
    )


@pytest.mark.parametrize(
    "message",
    [
        "Compare both repos",
        "Give me a unified report across repositories",
        "Analyze both projects and summarize",
    ],
)
def test_is_cross_repo_question_detects_compare_intent(message: str) -> None:
    assert is_cross_repo_question(message)


def test_match_projects_in_message_finds_named_repos() -> None:
    projects = [_project("p1", "acme/api"), _project("p2", "acme/web")]
    matched = match_projects_in_message("How do acme/api and acme/web differ?", projects)
    assert [p.id for p in matched] == ["p1", "p2"]


def test_resolve_cross_repo_projects_uses_explicit_ids() -> None:
    projects = [_project("p1", "acme/api"), _project("p2", "acme/web"), _project("p3", "acme/mobile")]
    resolved = resolve_cross_repo_projects(
        "What is the tech stack?",
        projects[0],
        projects,
        ["p1", "p3"],
    )
    assert [p.id for p in resolved] == ["p1", "p3"]


def test_resolve_cross_repo_projects_all_when_compare_both() -> None:
    projects = [_project("p1", "acme/api"), _project("p2", "acme/web")]
    resolved = resolve_cross_repo_projects("Compare both repos", projects[0], projects, None)
    assert [p.id for p in resolved] == ["p1", "p2"]


def test_resolve_cross_repo_projects_skips_single_repo_commit_compare() -> None:
    projects = [_project("p1", "acme/api"), _project("p2", "acme/web")]
    resolved = resolve_cross_repo_projects(
        "Compare the last 5 commits and tell me how the code evolved",
        projects[0],
        projects,
        None,
    )
    assert resolved == []


@pytest.mark.parametrize(
    "message",
    [
        "compare the last 3 commits",
        "how did the code evolve in the last five commits",
    ],
)
def test_is_single_repo_commit_scope(message: str) -> None:
    assert is_single_repo_commit_scope(message)


@pytest.mark.asyncio
async def test_process_cross_repo_message_sanitizes_known_shas() -> None:
    user = _make_user()
    projects = [_project("p1", "acme/api"), _project("p2", "acme/web")]
    canonical = "a" * 40
    snapshots = [
        {
            "project_id": "p1",
            "repo": "acme/api",
            "branch": "main",
            "stats": {},
            "recent_commits": [{"sha": canonical, "title": "feat", "author": "dev", "date": ""}],
            "languages": {},
        },
        {
            "project_id": "p2",
            "repo": "acme/web",
            "branch": "main",
            "stats": {},
            "recent_commits": [],
            "languages": {},
        },
    ]

    with (
        patch(
            "app.services.cross_repo.gather_cross_repo_snapshots",
            new_callable=AsyncMock,
            return_value=snapshots,
        ),
        patch("app.services.cross_repo.is_llm_configured", return_value=True),
        patch("app.services.cross_repo._search_memory", return_value=[]),
        patch(
            "app.services.cross_repo.chat_completion",
            new_callable=AsyncMock,
            return_value=f"Latest commit is {canonical}.",
        ),
    ):
        result = await process_cross_repo_message(
            user,
            "Compare both repos",
            projects,
            sibyl_enabled=False,
        )

    assert result["source"] == "cross_repo"
    assert canonical in result["reply"]


@pytest.mark.asyncio
async def test_process_cross_repo_message_without_llm() -> None:
    user = _make_user()
    projects = [_project("p1", "acme/api"), _project("p2", "acme/web")]
    snapshots = [
        {
            "project_id": "p1",
            "repo": "acme/api",
            "branch": "main",
            "stats": {
                "repo": "acme/api",
                "branch": "main",
                "commit_count": 120,
                "contributor_count": 3,
                "contributors": [],
            },
            "recent_commits": [],
            "languages": {"Python": 1000},
        },
        {
            "project_id": "p2",
            "repo": "acme/web",
            "branch": "main",
            "stats": {
                "repo": "acme/web",
                "branch": "main",
                "commit_count": 80,
                "contributor_count": 2,
                "contributors": [],
            },
            "recent_commits": [],
            "languages": {"TypeScript": 2000},
        },
    ]

    with (
        patch(
            "app.services.cross_repo.gather_cross_repo_snapshots",
            new_callable=AsyncMock,
            return_value=snapshots,
        ),
        patch("app.services.cross_repo.is_llm_configured", return_value=False),
        patch("app.services.cross_repo._search_memory", return_value=[]),
    ):
        result = await process_cross_repo_message(
            user,
            "Compare both repos",
            projects,
            sibyl_enabled=False,
        )

    assert result["source"] == "cross_repo"
    assert "acme/api" in result["reply"]
    assert "acme/web" in result["reply"]
    assert result["evidence"]
