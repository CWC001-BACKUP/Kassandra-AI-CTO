from app.services.evidence import commit_evidence_refs, commit_manifest_evidence_refs
from app.services.evidence_integrity import (
    build_commit_context_annotations,
    build_evidence_discrepancy_notes,
    find_prior_unavailability_claim,
    find_sha_discrepancy,
    format_evidence_escalation_note,
    validate_canonical_sha,
)
from app.services.repo_context import answer_commit_file_list, answer_contributor_count


def test_validate_canonical_sha_accepts_short_prefix() -> None:
    canonical = "ef420cc4e887f2d7f1ae6da1d8be3f77154a52cc"
    result = validate_canonical_sha("ef420cc", canonical)
    assert result["valid"] is True
    assert result["conflict"] is False


def test_validate_canonical_sha_flags_synthesized_full_sha() -> None:
    canonical = "ef420cc4e887f2d7f1ae6da1d8be3f77154a52cc"
    synthesized = "ef420cc" + "0" * 33
    result = validate_canonical_sha(synthesized, canonical)
    assert result["conflict"] is True
    assert result["message"] is not None
    assert "DISCREPANCY" in result["message"]


def test_find_sha_discrepancy_in_history() -> None:
    canonical = "ef420cc4e887f2d7f1ae6da1d8be3f77154a52cc"
    history = [
        {
            "role": "assistant",
            "content": (
                "Latest commit ef420cc full SHA "
                f"ef420cc{'0' * 33} was pushed today."
            ),
        }
    ]
    detail = {"sha": canonical, "short_sha": "ef420cc"}
    note = find_sha_discrepancy(history, detail)
    assert note is not None
    assert "ef420cc0" in note
    assert canonical in note


def test_find_prior_unavailability_claim() -> None:
    history = [
        {
            "role": "assistant",
            "content": (
                "Commit 89da7fb metadata is available, but the specific files "
                "changed cannot be enumerated from the available evidence."
            ),
        }
    ]
    detail = {
        "short_sha": "89da7fb",
        "sha": "89da7fb" + "a" * 33,
        "file_count": 30,
        "files": [{"filename": "src/main.py"}],
    }
    assert find_prior_unavailability_claim(history, detail) is True


def test_format_evidence_escalation_note() -> None:
    note = format_evidence_escalation_note(
        prior_unavailable=True,
        deep_retrieval=True,
        file_count=30,
    )
    assert note is not None
    assert "EVIDENCE ESCALATION" in note
    assert "30" in note


def test_build_commit_context_annotations_combines_notes() -> None:
    history = [
        {
            "role": "assistant",
            "content": (
                "Commit 89da7fb changed 5 files, but the file list is unavailable."
            ),
        }
    ]
    detail = {
        "short_sha": "89da7fb",
        "sha": "89da7fb" + "b" * 33,
        "file_count": 30,
        "files": [{"filename": f"f{i}.py"} for i in range(30)],
    }
    annotations = build_commit_context_annotations(
        history,
        "can you check and fetch those files?",
        detail,
    )
    assert "EVIDENCE ESCALATION" in annotations


def test_answer_commit_file_list_with_preamble() -> None:
    detail = {
        "short_sha": "89da7fb",
        "title": "big change",
        "file_count": 2,
        "files": [
            {"filename": "a.py", "status": "added", "additions": 1, "deletions": 0},
            {"filename": "b.py", "status": "modified", "additions": 2, "deletions": 1},
        ],
    }
    preamble = "EVIDENCE ESCALATION: deeper retrieval performed."
    reply = answer_commit_file_list(detail, branch="dev", preamble=preamble)
    assert preamble in reply
    assert "2 files" in reply
    assert "a.py" in reply


def test_answer_contributor_count_scoped_language() -> None:
    reply = answer_contributor_count(
        {
            "repo": "acme/api",
            "branch": "dev",
            "commit_count": 5,
            "contributor_count": 1,
            "contributors": [{"login": "alice", "contributions": 10}],
        }
    )
    assert "repository-wide" in reply
    assert "dev" in reply
    assert "separate" in reply.lower()


def test_commit_manifest_evidence_refs() -> None:
    detail = {
        "sha": "abc1234" + "0" * 33,
        "short_sha": "abc1234",
        "files": [
            {
                "filename": "src/app.py",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
            }
        ],
    }
    refs = commit_manifest_evidence_refs(detail, "acme/api")
    assert any(r.get("kind") == "manifest" for r in refs)
    assert any("src/app.py" in (r.get("label") or "") for r in refs)


def test_commit_evidence_refs_includes_manifest() -> None:
    detail = {
        "sha": "abc1234" + "0" * 33,
        "short_sha": "abc1234",
        "file_count": 1,
        "files": [{"filename": "README.md", "status": "added", "additions": 1, "deletions": 0}],
        "has_diff": True,
    }
    refs = commit_evidence_refs(detail, "acme/api")
    kinds = {r.get("kind") for r in refs}
    assert "manifest" in kinds
    assert "diff" in kinds


def test_build_evidence_discrepancy_notes_file_count() -> None:
    history = [
        {
            "role": "assistant",
            "content": "Commit 89da7fb changed 23 files in the configuration overhaul.",
        }
    ]
    detail = {"short_sha": "89da7fb", "sha": "89da7fb" + "0" * 33, "file_count": 19}
    notes = build_evidence_discrepancy_notes(history, detail)
    assert len(notes) >= 1
    assert any("23" in n and "19" in n for n in notes)
