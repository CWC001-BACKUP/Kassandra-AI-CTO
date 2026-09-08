from app.services.evidence_integrity import (
    EvidenceLevel,
    build_self_correction_preamble,
    collect_known_shas,
    find_author_discrepancy,
    find_memory_git_conflicts,
    find_stats_discrepancy,
    infer_evidence_level,
    sanitize_llm_reply,
)
from app.services.repo_context import (
    answer_file_history,
    extract_file_path_from_message,
    extract_symbol_from_message,
    format_file_history_block,
    is_file_history_question,
)


def test_is_file_history_question() -> None:
    assert is_file_history_question("when was speech functionality introduced?")
    assert is_file_history_question("when did src/app.py change?")
    assert not is_file_history_question("what is the latest commit?")


def test_extract_file_path_and_symbol() -> None:
    assert extract_file_path_from_message("when was src/speech.py introduced?") == "src/speech.py"
    assert extract_symbol_from_message("when was the processAudio function introduced?") == "processAudio"


def test_format_file_history_block() -> None:
    trace = {
        "found": True,
        "file_path": "src/speech.py",
        "branch": "dev",
        "commits_analyzed": 50,
        "introduction": {
            "sha": "abc1234" + "0" * 33,
            "short_sha": "abc1234",
            "status": "added",
            "author": "alice",
            "date": "2026-01-01",
            "message": "Add speech",
        },
        "last_change": {
            "sha": "def5678" + "0" * 33,
            "short_sha": "def5678",
            "status": "modified",
            "author": "bob",
            "date": "2026-02-01",
            "message": "Update speech",
        },
        "symbol": "processAudio",
        "symbol_introduction": {
            "short_sha": "abc1234",
            "date": "2026-01-01",
            "message": "Add speech",
        },
    }
    block = format_file_history_block(trace)
    assert "VERIFIED" in block
    assert "abc1234" in block
    assert "processAudio" in block

    reply = answer_file_history(trace)
    assert "abc1234" in reply
    assert "processAudio" in reply


def test_find_author_discrepancy() -> None:
    history = [
        {
            "role": "assistant",
            "content": "Commit 89da7fb by wronguser updated the config.",
        }
    ]
    detail = {
        "short_sha": "89da7fb",
        "sha": "89da7fb" + "0" * 33,
        "author": "correctuser",
    }
    note = find_author_discrepancy(history, detail)
    assert note is not None
    assert "wronguser" in note
    assert "correctuser" in note


def test_find_stats_discrepancy() -> None:
    history = [
        {
            "role": "assistant",
            "content": "The dev branch has 99 commits so far.",
        }
    ]
    note = find_stats_discrepancy(history, {"branch": "dev", "commit_count": 27})
    assert note is not None
    assert "99" in note
    assert "27" in note


def test_find_memory_git_conflicts() -> None:
    hits = [{"content": "The repo has only one contributor and 3 commits on dev."}]
    notes = find_memory_git_conflicts(
        hits,
        stats={"branch": "dev", "commit_count": 27, "contributor_count": 4},
    )
    assert notes
    assert any("MEMORY/GIT CONFLICT" in n for n in notes)


def test_sanitize_llm_reply_replaces_synthesized_sha() -> None:
    canonical = "ef420cc4e887f2d7f1ae6da1d8be3f77154a52cc"
    synthesized = "ef420cc" + "0" * 33
    known = collect_known_shas({"sha": canonical, "short_sha": "ef420cc"})
    reply = f"The latest commit is {synthesized}."
    cleaned = sanitize_llm_reply(reply, known_shas=known, history=[])
    assert canonical in cleaned
    body = cleaned.split("\n\n")[-1]
    assert synthesized not in body


def test_build_self_correction_preamble() -> None:
    preamble = build_self_correction_preamble(
        ["DISCREPANCY NOTE: Earlier 23 files were reported."]
    )
    assert preamble is not None
    assert preamble.startswith("Correction:")


def test_infer_evidence_level() -> None:
    assert infer_evidence_level("session", is_session=True) == EvidenceLevel.CONVERSATION_MEMORY
    assert infer_evidence_level(
        "github", has_commit_detail=True
    ) == EvidenceLevel.DEEP_COMMIT_RETRIEVAL
    assert infer_evidence_level(
        "github", has_repo_history=True
    ) == EvidenceLevel.REPOSITORY_HISTORY
