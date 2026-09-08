from app.services.evidence import (
    commit_evidence_refs,
    merge_evidence,
    normalize_evidence,
    sibyl_memory_evidence,
)


def test_commit_evidence_refs_include_github_urls() -> None:
    detail = {
        "sha": "abc1234567890",
        "short_sha": "abc1234",
        "file_count": 2,
        "files": [
            {"filename": "src/auth.py"},
            {"filename": "README.md"},
        ],
        "has_diff": True,
    }
    refs = commit_evidence_refs(detail, "acme/api")
    assert refs[0]["url"] == "https://github.com/acme/api/commit/abc1234567890"
    file_ref = next(r for r in refs if r.get("kind") == "manifest_file")
    assert "src/auth.py" in file_ref["url"]


def test_sibyl_memory_evidence_is_separate() -> None:
    refs = sibyl_memory_evidence([{"content": "We chose PostgreSQL for durability."}])
    assert refs[0]["source"] == "sibyl"
    assert refs[0]["kind"] == "memory"
    assert "PostgreSQL" in refs[0]["label"]


def test_merge_evidence_dedupes() -> None:
    merged = merge_evidence(
        [{"label": "Commit abc1234", "source": "github"}],
        [{"label": "Commit abc1234", "source": "github"}],
        sibyl_memory_evidence([{"content": "Architecture note"}]),
    )
    labels = [r["label"] for r in merged]
    assert labels.count("Commit abc1234") == 1
    assert any(r["source"] == "sibyl" for r in merged)


def test_normalize_legacy_strings() -> None:
    refs = normalize_evidence(["Commit abc1234", "README"])
    assert refs[0]["label"] == "Commit abc1234"
    assert refs[0]["source"] == "github"
