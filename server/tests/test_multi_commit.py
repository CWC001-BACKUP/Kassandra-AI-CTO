import pytest

from app.services.commit_compare import (
    compare_multiple_commits,
    format_multi_commit_compare_block,
    order_commits_for_analysis,
)
from app.services.repo_context import (
    answer_cross_session_continuation,
    parse_recent_commit_count,
    resolve_commit_targets,
)


def test_parse_recent_commit_count() -> None:
    assert parse_recent_commit_count("compare the last 3 commits") == 3
    assert parse_recent_commit_count("last five commits") == 5
    assert parse_recent_commit_count("who made the last commit") is None


def test_resolve_last_three_commits_compare() -> None:
    targets = resolve_commit_targets(
        "can you check and compare between the last 3 commits?",
        [],
        stored_sha="89da7fb",
        stored_previous_sha="1a57fa1",
    )
    assert targets["intent"] == "multi_compare"
    assert targets["count"] == 3


def _three_commit_fixture() -> list[dict]:
    """Repository order: newest first (aaa), oldest last (ccc)."""
    return [
        {
            "sha": "aaa",
            "short_sha": "aaa",
            "title": "latest",
            "author": "alice",
            "date": "2026-07-22",
            "file_count": 2,
            "files": [{"filename": "shared.py"}, {"filename": "only_latest.py"}],
            "all_filenames": ["shared.py", "only_latest.py"],
        },
        {
            "sha": "bbb",
            "short_sha": "bbb",
            "title": "middle",
            "author": "bob",
            "date": "2026-07-15",
            "file_count": 2,
            "files": [{"filename": "shared.py"}, {"filename": "only_middle.py"}],
            "all_filenames": ["shared.py", "only_middle.py"],
        },
        {
            "sha": "ccc",
            "short_sha": "ccc",
            "title": "oldest",
            "author": "carol",
            "date": "2026-07-01",
            "file_count": 1,
            "files": [{"filename": "shared.py"}],
            "all_filenames": ["shared.py"],
        },
    ]


def test_order_commits_chronologically() -> None:
    details = _three_commit_fixture()
    ordering = order_commits_for_analysis(details)
    chrono_shas = [d["short_sha"] for d in ordering["chronological_order"]]
    assert chrono_shas == ["ccc", "bbb", "aaa"]
    repo_shas = [d["short_sha"] for d in ordering["repository_order"]]
    assert repo_shas == ["aaa", "bbb", "ccc"]


def test_compare_multiple_commits_file_evolution() -> None:
    details = _three_commit_fixture()
    result = compare_multiple_commits(details)
    chrono_shas = [c["short_sha"] for c in result["commits"]]
    assert chrono_shas == ["ccc", "bbb", "aaa"]
    assert "shared.py" in result["repeatedly_touched"]
    assert result["repeatedly_touched"]["shared.py"] == [0, 1, 2]
    assert "only_latest.py" in result["unique_per_commit"][2]
    assert "only_middle.py" in result["unique_per_commit"][1]
    assert result["unique_per_commit"][0] == []

    block = format_multi_commit_compare_block(details, result)
    assert "THREE-COMMIT ENGINEERING ANALYSIS" in block
    assert "CHRONOLOGICAL ORDER" in block
    assert "ccc (oldest)" in block
    assert "aaa (newest)" in block
    assert "THREE-WAY FILE MEMBERSHIP" in block
    assert "shared.py" in block
    assert "Commit 1:" not in block
    assert "Commit 2:" not in block


def test_three_way_membership_buckets() -> None:
    details = _three_commit_fixture()
    result = compare_multiple_commits(details)
    buckets = result["membership_buckets"]
    assert "only aaa" in buckets
    assert "only_latest.py" in buckets["only aaa"]
    assert "only bbb" in buckets
    assert "only_middle.py" in buckets["only bbb"]
    assert "all commits" in buckets
    assert "shared.py" in buckets["all commits"]


def test_spec_shas_chronological_order() -> None:
    """Commits from spec: 9ee7727 oldest, 1a57fa1 middle, 89da7fb newest."""
    details = [
        {
            "sha": "89da7fb" + "0" * 33,
            "short_sha": "89da7fb",
            "title": "newest",
            "author": "dev",
            "date": "2026-07-22",
            "file_count": 1,
            "files": [{"filename": "z.py"}],
            "all_filenames": ["z.py"],
        },
        {
            "sha": "1a57fa1" + "0" * 33,
            "short_sha": "1a57fa1",
            "title": "middle",
            "author": "dev",
            "date": "2026-07-15",
            "file_count": 1,
            "files": [{"filename": "y.py"}],
            "all_filenames": ["y.py"],
        },
        {
            "sha": "9ee7727" + "0" * 33,
            "short_sha": "9ee7727",
            "title": "oldest",
            "author": "dev",
            "date": "2026-07-01",
            "file_count": 1,
            "files": [{"filename": "x.py"}],
            "all_filenames": ["x.py"],
            "parent_shas": [],
        },
    ]
    result = compare_multiple_commits(details)
    timeline = " → ".join(c["short_sha"] for c in result["commits"])
    assert timeline == "9ee7727 → 1a57fa1 → 89da7fb"
    block = format_multi_commit_compare_block(details, result)
    oldest_pos = block.index("9ee7727 (oldest)")
    newest_pos = block.index("89da7fb (newest)")
    assert oldest_pos < newest_pos


def test_cross_session_continuation_concise() -> None:
    sessions = [
        {
            "title": "who made the last commit?",
            "messages": [
                {"role": "user", "content": "who made the last commit?"},
                {
                    "role": "assistant",
                    "content": "Commit: 89da7fb\nThe previous commit is 1a57fa1.",
                },
                {"role": "user", "content": "compare both commits"},
            ],
        }
    ]
    reply = answer_cross_session_continuation(
        sessions, repo_name="CWC001-lab/Kassandra_Trade_Engine"
    )
    assert "89da7fb" in reply
    assert "1a57fa1" in reply
    assert "Topics covered" in reply or "Where you left off" in reply
    assert "What should we do next?" in reply
    assert "• You:" not in reply
    assert "You asked" not in reply
    assert "Here's what I found" not in reply


def test_continuation_prefers_substantive_session_over_meta() -> None:
    from app.services.repo_context import pick_substantive_session

    meta = {
        "title": "hi, lets continue from where we left off in the last conv...",
        "messages": [
            {
                "role": "user",
                "content": "hi, lets continue from where we left off in the last conversation",
            },
            {
                "role": "assistant",
                "content": "Here's what I found in your other chat session(s):",
            },
        ],
    }
    substantive = {
        "title": "How does authentication work?",
        "messages": [
            {"role": "user", "content": "can you show me the files affected?"},
            {"role": "assistant", "content": "Commit 89da7fb touches api/server.py"},
            {"role": "user", "content": "can you do a check and compare between both commits?"},
        ],
    }
    picked = pick_substantive_session([meta, substantive])
    assert picked is not None
    assert picked["title"] == "How does authentication work?"

    reply = answer_cross_session_continuation(
        [meta, substantive],
        repo_name="CWC001-lab/Kassandra_Trade_Engine",
    )
    assert "89da7fb" in reply
    assert "compare the commits" in reply.lower()
    assert "Here's what I found" not in reply


@pytest.mark.asyncio
async def test_chat_compare_last_three_fetches_from_github() -> None:
    from unittest.mock import AsyncMock, patch

    from app.models import Project, User
    from app.services.chat import process_chat_message

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

    shas = ["sha1" + "0" * 33, "sha2" + "0" * 33, "sha3" + "0" * 33]

    def _detail(sha: str, title: str, files: list[str], date: str) -> dict:
        return {
            "sha": sha,
            "short_sha": sha[:7],
            "title": title,
            "author": "dev",
            "date": date,
            "file_count": len(files),
            "files": [{"filename": f} for f in files],
            "all_filenames": files,
            "has_diff": False,
        }

    commits = [
        _detail(shas[0], "latest", ["a.py", "shared.py"], "2026-07-22"),
        _detail(shas[1], "middle", ["shared.py"], "2026-07-15"),
        _detail(shas[2], "oldest", ["b.py"], "2026-07-01"),
    ]

    with (
        patch("app.services.chat.is_llm_configured", return_value=False),
        patch(
            "app.services.chat.fetch_recent_commit_shas",
            new_callable=AsyncMock,
            return_value=shas,
        ),
        patch(
            "app.services.chat.fetch_multi_compare_context",
            new_callable=AsyncMock,
            return_value={
                "commits": commits,
                "formatted": "THREE-COMMIT ENGINEERING ANALYSIS",
                "evidence": [{"label": "3-commit comparison", "source": "github"}],
            },
        ),
    ):
        result = await process_chat_message(
            user,
            "can you check and compare between the last 3 commits?",
            project,
            stored_commit_sha=shas[0],
            stored_previous_commit_sha=shas[1],
        )

    assert result["source"] == "github"
    assert "3 commits" in result["reply"].lower() or "analysis" in result["reply"].lower()
