from unittest.mock import AsyncMock, patch

import pytest

from app.models import Project, User
from app.services.chat import process_chat_message
from app.services.github import trace_file_history, _paths_match


def test_paths_match() -> None:
    assert _paths_match("src/app.py", "./src/app.py")
    assert _paths_match("src/app.py", "app.py") is False


@pytest.mark.asyncio
async def test_trace_file_history_finds_introduction() -> None:
    sha_old = "aaa1111" + "0" * 33
    sha_new = "bbb2222" + "0" * 33

    async def fake_list_shas(token, repo, branch="main", max_commits=200, per_page=100):
        return [sha_new, sha_old]

    async def fake_list_commits(token, repo, branch="main", per_page=20):
        return [
            {
                "sha": sha_new,
                "title": "Update speech",
                "author": "bob",
                "date": "2026-02-01",
            },
            {
                "sha": sha_old,
                "title": "Add speech",
                "author": "alice",
                "date": "2026-01-01",
            },
        ]

    async def fake_file_stats(token, repo, sha, include_patch=False):
        if sha == sha_old:
            return [
                {
                    "filename": "src/speech.py",
                    "status": "added",
                    "additions": 40,
                    "deletions": 0,
                    "changes": 40,
                    "patch": "+def processAudio(): pass" if include_patch else None,
                }
            ]
        if sha == sha_new:
            return [
                {
                    "filename": "src/speech.py",
                    "status": "modified",
                    "additions": 2,
                    "deletions": 1,
                    "changes": 3,
                }
            ]
        return []

    with (
        patch("app.services.github.list_commit_shas", new=AsyncMock(side_effect=fake_list_shas)),
        patch("app.services.github.list_commits", new=AsyncMock(side_effect=fake_list_commits)),
        patch("app.services.github.get_commit_file_stats", new=AsyncMock(side_effect=fake_file_stats)),
    ):
        trace = await trace_file_history(
            "token",
            "acme/api",
            "src/speech.py",
            branch="dev",
            symbol="processAudio",
        )

    assert trace["found"] is True
    assert trace["introduction"]["short_sha"] == "aaa1111"
    assert trace["introduction"]["status"] == "added"
    assert trace["symbol_introduction"]["symbol"] == "processAudio"


@pytest.mark.asyncio
async def test_chat_file_history_route() -> None:
    user = User(
        id="user-1",
        email="dev@example.com",
        full_name="Dev",
        github_username="devuser",
        github_access_token="gh-token",
        is_verified=True,
    )
    project = Project(
        id="proj-1",
        user_id="user-1",
        repo_full_name="acme/api",
        repo_url="https://github.com/acme/api",
        default_branch="dev",
        is_active=True,
    )
    trace = {
        "found": True,
        "file_path": "src/speech.py",
        "branch": "dev",
        "commits_analyzed": 10,
        "introduction": {
            "short_sha": "abc1234",
            "sha": "abc1234" + "0" * 33,
            "status": "added",
            "author": "alice",
            "date": "2026-01-01",
            "message": "Add speech",
        },
        "last_change": {
            "short_sha": "abc1234",
            "sha": "abc1234" + "0" * 33,
            "status": "added",
            "author": "alice",
            "date": "2026-01-01",
            "message": "Add speech",
        },
        "evidence": [{"label": "Introduction commit abc1234", "source": "github"}],
    }

    with patch(
        "app.services.chat.fetch_file_history_context",
        new_callable=AsyncMock,
        return_value=trace,
    ):
        result = await process_chat_message(
            user,
            "when was src/speech.py introduced?",
            project,
        )

    assert result["source"] == "github"
    assert result["evidence_level"] == 3
    assert "abc1234" in result["reply"]
