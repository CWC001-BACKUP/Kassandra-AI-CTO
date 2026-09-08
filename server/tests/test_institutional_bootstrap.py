"""Tests for institutional memory bootstrap (architecture extract + gaps + store)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.services import memory as memory_module
from app.services.architecture_extract import (
    architecture_memories_from_stack,
    classify_commit_signal,
    extract_stack_from_manifests,
    is_meaningful_commit_message,
)
from app.services.history_bootstrap import detect_knowledge_gaps, run_bootstrap_ingestion
from app.services.institutional_memory import (
    build_memory,
    build_understanding_report,
    list_memories,
    store_memory,
)
from app.services.teach import looks_like_institutional_statement


@pytest.fixture()
def sibyl_tmpdir(tmp_path: Path):
    memory_module._provider_cache.clear()
    get_settings.cache_clear()
    with patch.object(get_settings(), "sibyl_data_dir", str(tmp_path)):
        yield tmp_path
    memory_module._provider_cache.clear()
    get_settings.cache_clear()


def test_extract_stack_from_package_json():
    pkg = (
        '{"dependencies":{"react":"18","express":"4","pg":"8",'
        '"jsonwebtoken":"9","jest":"29","@prisma/client":"5"}}'
    )
    stack = extract_stack_from_manifests(
        {"package.json": pkg},
        root_files=["Dockerfile", "package.json"],
        languages={"TypeScript": 1000},
        readme="REST API with JWT",
    )
    assert "React" in stack["frontend"]
    assert "Express" in stack["backend"]
    assert any("PostgreSQL" in x or "Prisma" in x for x in stack["database"])
    assert "JWT" in stack["authentication"]
    assert "Docker" in stack["infrastructure"]
    assert "Jest" in stack["testing"]


def test_meaningful_commit_classification():
    assert is_meaningful_commit_message("Migrate database from MongoDB to PostgreSQL")
    assert classify_commit_signal("Migrate database from MongoDB to PostgreSQL") == "migration"
    assert not is_meaningful_commit_message("chore: bump deps")


def test_knowledge_gaps_prioritize_why(sibyl_tmpdir: Path):
    stack = {"database": ["PostgreSQL"], "api": ["REST"], "authentication": ["JWT"]}
    gaps = detect_knowledge_gaps(
        stack=stack,
        history_memories=[],
        inferred_memories=[],
        project_id="p1",
    )
    questions = " ".join(g["question"] for g in gaps).lower()
    assert "postgresql" in questions or "database" in questions
    assert any((g.get("priority") or "").lower() == "high" for g in gaps)


def test_store_and_list_institutional_memory(sibyl_tmpdir: Path):
    tenant = "acme/demo"
    mem = build_memory(
        memory_type="observation",
        title="Frontend: React",
        content="React observed in package.json",
        source="repository_analysis",
        confidence="observed",
        tags=["architecture", "frontend"],
    )
    stored = store_memory(tenant, mem)
    assert stored.get("memory_id")
    listed = list_memories(tenant)
    assert any(m.get("title") == "Frontend: React" for m in listed)


def test_bootstrap_ingestion_writes_summary(sibyl_tmpdir: Path):
    tenant = "acme/demo2"
    pkg = '{"dependencies":{"react":"18","express":"4","pg":"8"}}'
    report = run_bootstrap_ingestion(
        tenant_id=tenant,
        project_id="p1",
        repo_full_name=tenant,
        languages={"TypeScript": 10},
        root_files=["package.json", "Dockerfile"],
        config_snippets={"package.json": pkg},
        readme="# Demo\nREST API",
        history_memories=[],
        inferred_memories=[],
        history_meta={"history_available": True, "commits_scanned": 0},
    )
    assert report["repo_full_name"] == tenant
    assert report["counts"]["observed"] >= 1
    assert len(report["knowledge_gaps"]) >= 1
    again = build_understanding_report(tenant, tenant)
    assert again["architecture"] or again["counts"]["observed"] >= 1


def test_teach_statement_detection():
    assert looks_like_institutional_statement(
        "We originally used MongoDB but migrated to PostgreSQL because of consistency problems."
    )
    assert not looks_like_institutional_statement("hi there")


def test_architecture_memories_are_observed():
    stack = extract_stack_from_manifests(
        {"package.json": '{"dependencies":{"react":"18"}}'},
        root_files=["package.json"],
        languages={},
        readme=None,
    )
    mems = architecture_memories_from_stack(stack, project_id=None, repo_full_name="o/r")
    assert mems
    assert all(m["confidence"] == "observed" for m in mems)
