import pytest

from app.services.repo_context import (
    _parse_package_json,
    answer_last_commit_author,
    is_commit_change_question,
    is_commit_count_question,
    is_contributor_question,
    is_last_commit_author_question,
    is_project_name_question,
    is_recent_changes_question,
    needs_commit_history,
    needs_stack_inspection,
)
from app.services.chat import _clean_response


def test_project_name_question_detected() -> None:
    assert is_project_name_question("what's the name of my project")


def test_commit_history_detected() -> None:
    assert needs_commit_history("what changed recently?")
    assert needs_commit_history("who made the last commit")


def test_recent_changes_question() -> None:
    assert is_recent_changes_question("What changed recently?")


def test_last_commit_author_question() -> None:
    assert is_last_commit_author_question("who made the last commit?")
    assert is_last_commit_author_question("who made the last commits?")


def test_commit_count_question() -> None:
    assert is_commit_count_question("how many commits in total are in this repo?")


def test_first_commit_question() -> None:
    from app.services.repo_context import is_first_commit_question

    assert is_first_commit_question("what was the first commit?")
    assert not is_first_commit_question("when was the repo created?")


def test_contributor_question() -> None:
    assert is_contributor_question("how many people have made commits to this repo?")


def test_commit_change_question_variants() -> None:
    assert is_commit_change_question("can you show me what was commited last?")
    assert is_commit_change_question("what was committed in the last commit?")


def test_conversation_recap_question() -> None:
    from app.services.repo_context import answer_conversation_recap, is_conversation_recap_question

    assert is_conversation_recap_question("what were we talking about previously?")
    reply = answer_conversation_recap(
        [{"role": "user", "content": "how many commits?", "source": None}]
    )
    assert "Commit count" in reply or "how many commits" in reply


def test_repo_created_question() -> None:
    from app.services.repo_context import is_repo_created_question

    assert is_repo_created_question("when was the repo created?")


def test_file_churn_question() -> None:
    from app.services.repo_context import is_file_churn_question

    assert is_file_churn_question("what file was updated the most?")


def test_continuation_phrase_detected() -> None:
    from app.services.repo_context import (
        implies_other_session,
        is_conversation_recap_question,
        should_load_other_sessions,
    )

    msg = "hi, lets continue from where we left off in the last conversation"
    assert is_conversation_recap_question(msg)
    assert implies_other_session(msg, [])
    assert should_load_other_sessions(msg, [])

    from app.services.repo_context import is_cross_session_question, parse_time_hint

    assert is_cross_session_question("it was in another session")
    assert is_cross_session_question("what about in other sessions")
    assert implies_other_session("what were we talking about before", [])
    assert parse_time_hint("message around 10:11 am today") is not None


def test_other_sessions_follow_up() -> None:
    from app.services.repo_context import (
        implies_other_session,
        is_cross_session_question,
        should_load_other_sessions,
    )

    history = [
        {"role": "user", "content": "Hi, what were we talking about before"},
        {
            "role": "assistant",
            "content": "We've just started this chat session — there isn't any prior conversation.",
        },
    ]
    msg = "what about in other sessions"
    assert is_cross_session_question(msg)
    assert implies_other_session(msg, history)
    assert should_load_other_sessions(msg, history)


def test_stack_inspection() -> None:
    assert needs_stack_inspection("what is the app current stack")


def test_parse_package_json_extracts_deps() -> None:
    content = '{"name":"api","dependencies":{"express":"^4.18.2","mongoose":"^8.0.0"}}'
    parsed = _parse_package_json(content)
    assert parsed["name"] == "api"
    assert "express" in parsed["dependencies"]


def test_answer_last_commit_author() -> None:
    ctx = {
        "repo": "org/repo",
        "commits": [
            {
                "sha": "abc1234",
                "title": "fix: auth",
                "author": "david",
                "date": "2026-08-30",
            }
        ],
    }
    reply = answer_last_commit_author(ctx)
    assert reply is not None
    text, sha = reply
    assert "david" in text
    assert "abc123" in text
    assert sha == "abc1234"


def test_clean_response_strips_tool_leakage() -> None:
    raw = (
        "We need to call repo_browser.get_recent_commits.\n"
        "The last commit was by Alice."
    )
    cleaned = _clean_response(raw)
    assert "repo_browser" not in cleaned
    assert "Alice" in cleaned
