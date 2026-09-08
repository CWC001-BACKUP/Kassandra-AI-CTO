from unittest.mock import AsyncMock, patch

import pytest

from app.models import Project, User
from app.services.chat import process_chat_message
from app.services.github import get_oldest_commit_on_branch
from app.services.repo_context import (
    answer_commit_endpoints_without_llm,
    answer_first_commit_without_llm,
    answer_parent_commit,
    find_commit_count_discrepancy,
    is_commit_endpoints_question,
    is_first_commit_question,
    is_parent_commit_question,
)


def test_first_commit_question_detection() -> None:
    assert is_first_commit_question("what was the very first commit?")
    assert is_first_commit_question("show me the initial commit in the repo")
    assert is_first_commit_question("what is the oldest commit on dev?")
    assert not is_first_commit_question("who made the last commit?")


def test_commit_endpoints_question_detection() -> None:
    msg = "what was the first and last commit to this repo and who made them"
    assert is_commit_endpoints_question(msg)
    assert not is_first_commit_question(msg)
    assert is_commit_endpoints_question("show me the oldest and newest commits")
    assert not is_commit_endpoints_question("what was the very first commit?")


def test_answer_commit_endpoints_without_llm() -> None:
    first = {
        "short_sha": "9ee7727",
        "sha": "9ee7727" + "0" * 33,
        "author": "alice",
        "date": "2026-01-01",
        "title": "Initial commit",
    }
    latest = {
        "sha": "89da7fb" + "0" * 33,
        "author": "david",
        "date": "2026-07-01",
        "title": "Latest work",
    }
    reply = answer_commit_endpoints_without_llm(first, latest, branch="dev", total_commits=27)
    assert "9ee7727" in reply
    assert "alice" in reply
    assert "89da7fb" in reply
    assert "david" in reply
    assert "27" in reply


def test_parent_commit_question_detection() -> None:
    assert is_parent_commit_question("what is the parent of commit 89da7fb?")
    assert is_parent_commit_question("parent of the last commit")
    assert not is_parent_commit_question("what changed in the last commit?")


def test_find_commit_count_discrepancy() -> None:
    history = [
        {
            "role": "assistant",
            "content": "Commit 89da7fb changed 23 files in the configuration overhaul.",
        }
    ]
    detail = {"short_sha": "89da7fb", "sha": "89da7fb" + "0" * 33, "file_count": 19}
    note = find_commit_count_discrepancy(history, detail)
    assert note is not None
    assert "23" in note
    assert "19" in note


def test_answer_first_commit_without_llm() -> None:
    detail = {
        "short_sha": "9ee7727",
        "sha": "9ee7727" + "0" * 33,
        "author": "dev",
        "date": "2026-01-01",
        "title": "Initial commit",
        "file_count": 3,
        "files": [{"filename": "README.md"}, {"filename": "main.py"}],
        "parent_shas": [],
    }
    reply = answer_first_commit_without_llm(detail, branch="dev", total_commits=27)
    assert "9ee7727" in reply
    assert "27" in reply
    assert "root" in reply.lower()


def test_answer_parent_commit() -> None:
    detail = {
        "short_sha": "89da7fb",
        "parent_shas": ["1a57fa1" + "0" * 33],
    }
    reply = answer_parent_commit(detail, branch="dev")
    assert "1a57fa1" in reply

    root = answer_parent_commit({"short_sha": "9ee7727", "parent_shas": []}, branch="dev")
    assert "no parent" in root.lower()


@pytest.mark.asyncio
async def test_get_oldest_commit_on_branch_paginates() -> None:
    page1 = [{"sha": f"new{i}", "commit": {"message": "m", "author": {"name": "a", "date": "2026-07-01"}}} for i in range(2)]
    page2 = [{"sha": f"old{i}", "commit": {"message": "m", "author": {"name": "a", "date": "2026-01-01"}}} for i in range(2)]

    async def fake_get(token, path, params=None):
        class Resp:
            def __init__(self, data, link=""):
                self._data = data
                self.headers = {"Link": link}
                self.status_code = 200

            def json(self):
                return self._data

        if params and params.get("page") == 2:
            return Resp(page2)
        return Resp(
            page1,
            link='<https://api.github.com?page=2>; rel="next", <https://api.github.com?page=2>; rel="last"',
        )

    with patch("app.services.github._github_get", new=AsyncMock(side_effect=fake_get)):
        oldest = await get_oldest_commit_on_branch("token", "acme/api", branch="dev")

    assert oldest is not None
    assert oldest["sha"] == "old1"


@pytest.mark.asyncio
async def test_chat_first_commit_fetches_from_github() -> None:
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
    first_sha = "9ee7727" + "0" * 33
    detail = {
        "sha": first_sha,
        "short_sha": "9ee7727",
        "title": "Initial commit",
        "author": "dev",
        "date": "2026-01-01",
        "file_count": 2,
        "files": [{"filename": "README.md"}],
        "parent_shas": [],
        "has_diff": False,
    }

    with (
        patch("app.services.chat.is_llm_configured", return_value=False),
        patch(
            "app.services.chat.fetch_first_commit_context",
            new_callable=AsyncMock,
            return_value={
                "commit": detail,
                "branch": "dev",
                "total_commits": 27,
                "formatted": "FIRST COMMIT ON DEV",
                "evidence": [{"label": "First commit on dev", "source": "github"}],
            },
        ),
    ):
        result = await process_chat_message(
            user,
            "what was the very first commit in this repository?",
            project,
        )

    assert result["source"] == "github"
    assert "9ee7727" in result["reply"]
    assert "27" in result["reply"]


@pytest.mark.asyncio
async def test_chat_commit_endpoints_fetches_from_github() -> None:
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
    first_sha = "9ee7727" + "0" * 33
    latest_sha = "89da7fb" + "0" * 33
    first_detail = {
        "sha": first_sha,
        "short_sha": "9ee7727",
        "title": "Initial commit",
        "author": "alice",
        "date": "2026-01-01",
        "file_count": 2,
        "files": [{"filename": "README.md"}],
        "parent_shas": [],
        "has_diff": False,
    }
    latest_commit = {
        "sha": latest_sha,
        "author": "david",
        "date": "2026-07-01",
        "title": "Latest work",
    }

    with (
        patch("app.services.chat.is_llm_configured", return_value=False),
        patch(
            "app.services.chat.fetch_commit_endpoints_context",
            new_callable=AsyncMock,
            return_value={
                "first": first_detail,
                "latest": latest_commit,
                "branch": "dev",
                "total_commits": 27,
                "formatted": "COMMIT ENDPOINTS ON DEV",
                "evidence": [
                    {"label": "First commit on dev", "source": "github"},
                    {"label": f"Commit {latest_sha[:7]} on dev", "source": "github"},
                ],
            },
        ),
    ):
        result = await process_chat_message(
            user,
            "what was the first and last commit to this repo and who made them",
            project,
        )

    assert result["source"] == "github"
    assert "9ee7727" in result["reply"]
    assert "alice" in result["reply"]
    assert "89da7fb" in result["reply"]
    assert "david" in result["reply"]
    assert result["last_commit_sha"] == latest_sha
