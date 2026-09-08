from unittest.mock import AsyncMock, patch

import pytest

from app.models import Project, User
from app.services.chat import process_chat_message


def _make_user() -> User:
    return User(
        id="user-1",
        email="dev@example.com",
        full_name="Dev User",
        github_username="devuser",
        github_access_token="gh-token",
        is_verified=True,
    )


def _make_project() -> Project:
    return Project(
        id="proj-1",
        user_id="user-1",
        repo_full_name="acme/api",
        repo_url="https://github.com/acme/api",
        default_branch="main",
        is_active=True,
    )


def _mock_ctx() -> dict:
    return {
        "repo": "acme/api",
        "branch": "main",
        "commits": [
            {
                "sha": "abc1234",
                "title": "fix: thing",
                "author": "devuser",
                "date": "2026-08-30",
            }
        ],
        "pull_requests": [],
        "evidence_sources": ["commit history", "package.json"],
    }


def _mock_commit_detail() -> dict:
    return {
        "sha": "abc1234567890abcdef",
        "short_sha": "abc1234",
        "title": "fix: thing",
        "author": "devuser",
        "date": "2026-08-30",
        "files": [{"filename": "src/auth.py", "status": "modified", "additions": 5, "deletions": 2}],
        "file_count": 1,
        "additions": 5,
        "deletions": 2,
        "diff_excerpt": "--- src/auth.py ---\n+token refresh",
        "has_diff": True,
    }


@pytest.mark.asyncio
async def test_chat_continue_from_last_conversation_uses_cross_session() -> None:
    user = _make_user()
    project = _make_project()
    other_sessions = [
        {
            "title": "who made the last commit?",
            "time_label": "1:15 PM",
            "messages": [
                {"role": "user", "content": "who made the last commit?"},
                {
                    "role": "assistant",
                    "content": "On the dev branch, the most recent commit was made by david.",
                },
            ],
        }
    ]

    result = await process_chat_message(
        user,
        "hi, lets continue from where we left off in the last conversation",
        project,
        history=[{"role": "assistant", "content": "Hello, welcome message", "source": "intro"}],
        other_sessions=other_sessions,
    )

    assert result["source"] == "session"
    assert result["intent"] is None
    assert "david" in result["reply"] or "compare" in result["reply"].lower()
    assert "Here's what I found in your other chat session" not in result["reply"]
    assert "Connect a GitHub repository" not in result["reply"]


@pytest.mark.asyncio
async def test_chat_other_sessions_follow_up() -> None:
    user = _make_user()
    project = _make_project()
    other_sessions = [
        {
            "title": "compare both commits",
            "time_label": "12:40 PM",
            "messages": [
                {"role": "user", "content": "can you compare both commits?"},
                {
                    "role": "assistant",
                    "content": "Commit 89da7fb changed 19 files compared with 1a57fa1.",
                },
            ],
        }
    ]
    history = [
        {"role": "user", "content": "Hi, what were we talking about before"},
        {
            "role": "assistant",
            "content": "We've just started this chat session — there isn't any prior conversation.",
            "source": "session",
        },
    ]

    result = await process_chat_message(
        user,
        "what about in other sessions",
        project,
        history=history,
        other_sessions=other_sessions,
    )

    assert result["source"] == "session"
    assert "89da7fb" in result["reply"] or "compare" in result["reply"].lower()
    assert "Topics covered" in result["reply"] or "Where you left off" in result["reply"]
    assert "You asked" not in result["reply"]
    assert result["evidence"][0]["label"] in (
        "Prior session context (not repository evidence)",
        "Cross-session history",
    )


@pytest.mark.asyncio
async def test_chat_recap_before_checks_other_sessions() -> None:
    user = _make_user()
    project = _make_project()
    other_sessions = [
        {
            "title": "how many commits",
            "time_label": "11:00 AM",
            "messages": [
                {"role": "user", "content": "how many commits are in this app"},
                {
                    "role": "assistant",
                    "content": "The repository has 27 commits on the dev branch.",
                },
            ],
        }
    ]

    result = await process_chat_message(
        user,
        "Hi, what were we talking about before",
        project,
        history=[{"role": "assistant", "content": "Welcome", "source": "intro"}],
        other_sessions=other_sessions,
    )

    assert result["source"] == "session"
    assert "27 commits" in result["reply"] or "Commit count" in result["reply"]
    assert "You asked" not in result["reply"]
    assert "just started this chat session" not in result["reply"].lower()


@pytest.mark.asyncio
async def test_chat_recap_before_after_failed_attempts_uses_other_sessions() -> None:
    user = _make_user()
    project = _make_project()
    other_sessions = [
        {
            "title": "compare both commits",
            "time_label": "12:40 PM",
            "messages": [
                {"role": "user", "content": "can you compare both commits?"},
                {
                    "role": "assistant",
                    "content": "Commit 89da7fb changed 19 files compared with 1a57fa1.",
                },
            ],
        }
    ]
    history = [
        {"role": "user", "content": "Hi, what were we talking about before"},
        {
            "role": "assistant",
            "content": "We've just started this chat session — there isn't any prior conversation.",
            "source": "session",
        },
        {"role": "user", "content": "what about in other sessions"},
        {
            "role": "assistant",
            "content": "I don't have any information about conversations from other sessions.",
            "source": "llm",
        },
    ]

    result = await process_chat_message(
        user,
        "Hi, what were we talking about before",
        project,
        history=history,
        other_sessions=other_sessions,
    )

    assert result["source"] == "session"
    assert "89da7fb" in result["reply"]
    assert "You asked" not in result["reply"]


@pytest.mark.asyncio
async def test_chat_greeting_uses_intro() -> None:
    user = _make_user()
    result = await process_chat_message(user, "hello", None)
    assert result["source"] == "intro"
    assert result["intent"] == "greeting"


@pytest.mark.asyncio
async def test_chat_last_commit_author_direct() -> None:
    user = _make_user()
    project = _make_project()

    with patch(
        "app.services.chat.gather_chat_context",
        new_callable=AsyncMock,
        return_value=_mock_ctx(),
    ):
        result = await process_chat_message(user, "who made the last commit?", project)

    assert result["source"] == "github"
    assert "devuser" in result["reply"]
    assert "repo_browser" not in result["reply"]
    assert result["last_commit_sha"] == "abc1234"


@pytest.mark.asyncio
async def test_chat_commit_change_follow_up() -> None:
    user = _make_user()
    project = _make_project()
    history = [
        {
            "role": "assistant",
            "content": "The most recent commit was made by devuser.\n\nCommit: abc1234\nMessage: fix: thing",
        }
    ]

    with (
        patch("app.services.chat.is_llm_configured", return_value=False),
        patch(
            "app.services.chat.fetch_commit_context",
            new_callable=AsyncMock,
            return_value={
                "commit": _mock_commit_detail(),
                "formatted": "Commit: abc1234",
                "evidence_sources": ["Commit abc1234", "src/auth.py"],
                "evidence": [
                    {"label": "Commit abc1234", "url": "https://github.com/acme/api/commit/abc1234", "source": "github", "kind": "commit"},
                    {"label": "src/auth.py", "url": None, "source": "github", "kind": "file"},
                ],
            },
        ),
    ):
        result = await process_chat_message(
            user,
            "what did the person change?",
            project,
            history=history,
            stored_commit_sha="abc1234",
        )

    assert result["source"] == "github"
    assert "src/auth.py" in result["reply"] or any(
        "auth.py" in (e.get("label") or "") for e in (result.get("evidence") or [])
    )
    assert any(
        "abc1234" in (e.get("label") or "") for e in (result.get("evidence") or [])
    )


@pytest.mark.asyncio
async def test_chat_what_was_committed_last() -> None:
    user = _make_user()
    project = _make_project()

    with (
        patch("app.services.chat.is_llm_configured", return_value=False),
        patch(
            "app.services.chat.fetch_commit_context",
            new_callable=AsyncMock,
            return_value={
                "commit": _mock_commit_detail(),
                "formatted": "Commit: abc1234",
                "evidence_sources": ["Commit abc1234", "Commit diff"],
            },
        ),
        patch(
            "app.services.chat.gather_chat_context",
            new_callable=AsyncMock,
            return_value=_mock_ctx(),
        ),
    ):
        result = await process_chat_message(
            user,
            "can you show me what was commited last?",
            project,
        )

    assert result["source"] == "github"
    assert result["last_commit_sha"]


@pytest.mark.asyncio
async def test_chat_commit_count_direct() -> None:
    user = _make_user()
    project = _make_project()
    stats = {
        "repo": "acme/api",
        "branch": "main",
        "commit_count": 142,
        "contributor_count": 5,
        "contributors": [{"login": "devuser", "contributions": 80}],
        "repo_meta": {},
    }

    with patch(
        "app.services.chat.gather_repo_stats",
        new_callable=AsyncMock,
        return_value=stats,
    ):
        result = await process_chat_message(
            user, "how many commits in total are in this repo?", project
        )

    assert result["source"] == "github"
    assert "142" in result["reply"]


@pytest.mark.asyncio
async def test_chat_ci_status_direct() -> None:
    user = _make_user()
    project = _make_project()
    mock_ctx = {
        **_mock_ctx(),
        "repo_activity": {
            "workflow_runs": [
                {
                    "name": "CI",
                    "branch": "main",
                    "conclusion": "failure",
                    "time": "1h ago",
                    "actor": "devuser",
                    "head_sha": "abc1234",
                }
            ],
            "failed_runs": [],
            "workflows": [{"name": "CI"}],
            "deployments": [],
            "releases": [],
            "events": [],
            "environments": [],
        },
        "evidence_sources": ["GitHub Actions runs"],
    }

    with patch(
        "app.services.chat.gather_chat_context",
        new_callable=AsyncMock,
        return_value=mock_ctx,
    ):
        result = await process_chat_message(user, "why did the build fail?", project)

    assert result["source"] == "github"
    assert "failure" in result["reply"]


@pytest.mark.asyncio
async def test_chat_contributor_count_direct() -> None:
    user = _make_user()
    project = _make_project()
    stats = {
        "repo": "acme/api",
        "branch": "main",
        "commit_count": 142,
        "contributor_count": 3,
        "contributors": [
            {"login": "alice", "contributions": 50},
            {"login": "bob", "contributions": 30},
            {"login": "carol", "contributions": 20},
        ],
        "repo_meta": {},
    }

    with patch(
        "app.services.chat.gather_repo_stats",
        new_callable=AsyncMock,
        return_value=stats,
    ):
        result = await process_chat_message(
            user, "how many people have made commits to this repo?", project
        )

    assert result["source"] == "github"
    assert "3" in result["reply"]
    assert "alice" in result["reply"]


@pytest.mark.asyncio
async def test_chat_conversation_recap() -> None:
    user = _make_user()
    project = _make_project()
    history = [
        {"role": "user", "content": "how many commits are in this repo", "source": None},
        {
            "role": "assistant",
            "content": "The repository has 69 commits on main.",
            "source": "github",
        },
    ]

    result = await process_chat_message(
        user,
        "what were we talking about previously?",
        project,
        history=history,
    )

    assert result["source"] == "session"
    assert "Commit count" in result["reply"] or "69 commits" in result["reply"]
    assert "You asked" not in result["reply"]
    assert result["evidence"][0]["label"] == "Chat session history"
    assert result["evidence"][0]["source"] == "session"


@pytest.mark.asyncio
async def test_chat_repo_created_direct() -> None:
    user = _make_user()
    project = _make_project()

    with patch(
        "app.services.chat.get_repo",
        new_callable=AsyncMock,
        return_value={
            "created_at": "2024-01-15T10:00:00Z",
            "pushed_at": "2026-08-21T19:12:45Z",
            "html_url": "https://github.com/acme/api",
        },
    ):
        result = await process_chat_message(
            user, "when was the repo created?", project
        )

    assert result["source"] == "github"
    assert "2024-01-15" in result["reply"]


@pytest.mark.asyncio
async def test_chat_cross_session_recap() -> None:
    user = _make_user()
    project = _make_project()
    other_sessions = [
        {
            "title": "how many commits in total are in this repo?",
            "time_label": "10:11 AM",
            "messages": [
                {
                    "role": "user",
                    "content": "what were we talking about previously?",
                    "source": None,
                },
                {
                    "role": "assistant",
                    "content": "We were just getting started with the welcome message.",
                    "source": "session",
                },
                {
                    "role": "user",
                    "content": "how many commits in total are in this repo?",
                    "source": None,
                },
                {
                    "role": "assistant",
                    "content": "The repository has 69 commits on the main branch.",
                    "source": "github",
                },
            ],
        }
    ]

    result = await process_chat_message(
        user,
        "it was in another session around 10:11 am",
        project,
        history=[],
        other_sessions=other_sessions,
    )

    assert result["source"] == "session"
    assert "Commit count" in result["reply"] or "69 commits" in result["reply"]
    assert result["evidence"][0]["label"] == "Cross-session history"
    assert result["evidence"][0]["source"] == "session"


@pytest.mark.asyncio
async def test_chat_without_llm_returns_memory_fallback() -> None:
    user = _make_user()
    project = _make_project()

    with (
        patch("app.services.chat.is_llm_configured", return_value=False),
        patch(
            "app.services.chat.gather_chat_context",
            new_callable=AsyncMock,
            return_value={**_mock_ctx(), "primary_language": "Python"},
        ),
        patch("app.services.chat._search_memory", return_value=[{"content": "Uses PostgreSQL"}]),
    ):
        result = await process_chat_message(user, "What database do we use?", project)

    assert result["source"] == "memory_only"
    assert "PostgreSQL" in result["reply"]


@pytest.mark.asyncio
async def test_chat_project_name_without_llm() -> None:
    user = _make_user()
    project = _make_project()

    result = await process_chat_message(user, "what's the name of my project", project)

    assert result["source"] == "system"
    assert "acme/api" in result["reply"]


@pytest.mark.asyncio
async def test_chat_with_llm() -> None:
    user = _make_user()
    project = _make_project()

    with (
        patch("app.services.chat.is_llm_configured", return_value=True),
        patch(
            "app.services.chat.gather_chat_context",
            new_callable=AsyncMock,
            return_value=_mock_ctx(),
        ),
        patch("app.services.chat._search_memory", return_value=[]),
        patch(
            "app.services.chat.chat_completion",
            new_callable=AsyncMock,
            return_value="We use PostgreSQL for reliability.",
        ),
    ):
        result = await process_chat_message(user, "What database?", project)

    assert result["source"] == "llm"
    assert "PostgreSQL" in result["reply"]


@pytest.mark.asyncio
async def test_chat_sibyl_disabled_skips_memory() -> None:
    user = _make_user()
    project = _make_project()

    with (
        patch("app.services.chat.is_llm_configured", return_value=False),
        patch(
            "app.services.chat.gather_chat_context",
            new_callable=AsyncMock,
            return_value={**_mock_ctx(), "primary_language": "Python"},
        ),
        patch("app.services.chat._search_memory") as mock_search,
    ):
        result = await process_chat_message(
            user,
            "What database do we use?",
            project,
            sibyl_enabled=False,
        )

    mock_search.assert_not_called()
    assert result["memory_hits"] == 0
    assert "Sibyl memory is OFF" in result["reply"]
