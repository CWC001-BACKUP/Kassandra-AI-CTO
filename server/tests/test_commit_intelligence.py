import pytest

from app.services.commit_compare import format_commit_compare_block
from app.services.repo_context import (
    answer_commit_file_list,
    answer_previous_commit,
    is_commit_compare_question,
    is_commit_file_list_question,
    is_previous_commit_question,
    resolve_commit_targets,
)


def test_previous_commit_question_detected() -> None:
    assert is_previous_commit_question("what was the commit before this one?")


def test_commit_compare_question_detected() -> None:
    assert is_commit_compare_question("can you check and compare between both commits?")
    assert is_commit_compare_question("compare 89da7fb and 1a57fa1")


def test_commit_file_list_question_detected() -> None:
    assert is_commit_file_list_question("check the file list for it then")


def test_resolve_commit_targets_prefers_previous_for_it() -> None:
    history = [
        {
            "role": "assistant",
            "content": "The commit before abc1234 is 1a57fa1 — auto trade settings.",
        }
    ]
    targets = resolve_commit_targets(
        "check the file list for it then",
        history,
        stored_sha="89da7fb1234567890abcdef",
        stored_previous_sha="1a57fa1abcdef1234567890",
    )
    assert targets["primary"] == "1a57fa1abcdef1234567890"


def test_resolve_commit_targets_compare_both() -> None:
    targets = resolve_commit_targets(
        "compare both commits",
        [],
        stored_sha="89da7fb",
        stored_previous_sha="1a57fa1",
    )
    assert targets["intent"] == "compare"
    assert targets["shas"] == ["89da7fb", "1a57fa1"]


def test_answer_previous_commit() -> None:
    ctx = {
        "repo": "org/repo",
        "branch": "dev",
        "commits": [
            {"sha": "abc1234", "title": "latest", "author": "alice", "date": "2026-07-22"},
            {"sha": "def5678", "title": "previous", "author": "bob", "date": "2026-07-03"},
        ],
    }
    reply, sha = answer_previous_commit(ctx, "abc1234")
    assert "dev branch" in reply
    assert sha == "def5678"
    assert "previous" in reply


def test_answer_commit_file_list_uses_authoritative_count() -> None:
    detail = {
        "short_sha": "1a57fa1",
        "title": "auto trade settings",
        "file_count": 12,
        "files": [{"filename": f"file{i}.py", "status": "modified", "additions": 1, "deletions": 0} for i in range(12)],
    }
    reply = answer_commit_file_list(detail, branch="dev")
    assert "12 files" in reply
    assert "file0.py" in reply


def test_format_commit_compare_block() -> None:
    detail_a = {
        "short_sha": "abc1234",
        "title": "commit A",
        "date": "2026-07-22",
        "file_count": 2,
        "files": [
            {"filename": "shared.py"},
            {"filename": "only_a.py"},
        ],
    }
    detail_b = {
        "short_sha": "def5678",
        "title": "commit B",
        "date": "2026-07-03",
        "file_count": 2,
        "files": [
            {"filename": "shared.py"},
            {"filename": "only_b.py"},
        ],
    }
    block = format_commit_compare_block(detail_a, detail_b)
    assert "FILES CHANGED IN BOTH" in block
    assert "FILES ONLY IN COMMIT A" in block
    assert "FILES ONLY IN COMMIT B" in block


@pytest.mark.asyncio
async def test_chat_file_list_follow_up_fetches_previous_commit() -> None:
    from unittest.mock import AsyncMock, patch

    from app.models import Project, User
    from app.services.chat import process_chat_message

    user = User(
        id="user-1",
        email="dev@example.com",
        full_name="Dev User",
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
    detail = {
        "sha": "1a57fa1abcdef",
        "short_sha": "1a57fa1",
        "title": "auto trade settings",
        "author": "devuser",
        "date": "2026-07-03",
        "files": [{"filename": "core/signal.py", "status": "modified", "additions": 3, "deletions": 1}],
        "file_count": 1,
        "has_diff": False,
    }

    with patch(
        "app.services.chat.fetch_commit_context",
        new_callable=AsyncMock,
        return_value={
            "commit": detail,
            "formatted": "Commit: 1a57fa1",
            "evidence_sources": ["Commit 1a57fa1", "1 files changed"],
        },
    ) as mock_fetch:
        result = await process_chat_message(
            user,
            "check the file list for it then",
            project,
            history=[
                {
                    "role": "assistant",
                    "content": "On the dev branch, the commit before abc1234 is:\n\nCommit: 1a57fa1",
                }
            ],
            stored_commit_sha="abc1234567890",
            stored_previous_commit_sha="1a57fa1abcdef",
        )

    mock_fetch.assert_called_once()
    assert mock_fetch.call_args[0][2] == "1a57fa1abcdef"
    assert result["source"] == "github"
    assert "core/signal.py" in result["reply"]
