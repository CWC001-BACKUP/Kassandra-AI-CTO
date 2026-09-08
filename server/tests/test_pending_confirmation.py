"""Pending confirmation must treat YES as a control action, not extraction input."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.services import memory as memory_module
from app.services.institutional_memory import build_memory, list_memories, store_memory
from app.services.pending_memory import (
    confirm_pending,
    create_pending,
    detect_confirmation_intent,
    get_active_pending,
    handle_pending_control_message,
)
from app.services.teach import extract_candidate_memories, teach_kassandra


@pytest.fixture()
def sibyl_tmpdir(tmp_path: Path):
    memory_module._provider_cache.clear()
    get_settings.cache_clear()
    with patch.object(get_settings(), "sibyl_data_dir", str(tmp_path)):
        yield tmp_path
    memory_module._provider_cache.clear()
    get_settings.cache_clear()


def test_yes_is_confirm_intent():
    intent, _ = detect_confirmation_intent("yes")
    assert intent == "confirm_all"
    intent, _ = detect_confirmation_intent("save it")
    assert intent == "confirm_all"
    intent, idxs = detect_confirmation_intent("save 1 and 3")
    assert idxs == [0, 2]
    assert intent == "select"
    intent, _ = detect_confirmation_intent("no")
    assert intent == "reject"


def test_yes_with_knowledge_is_confirm_with_knowledge():
    intent, _ = detect_confirmation_intent(
        "yes, the authorisation so i can have more users with normal keys "
        "and control them with master keys without oauth"
    )
    assert intent == "confirm_with_knowledge"


def test_yes_saves_pending_not_extracts_yes(sibyl_tmpdir: Path):
    tenant = "acme/pending"
    user_id = "user-1"
    project_id = "proj-1"
    cand = build_memory(
        memory_type="architectural_decision",
        title="Flask REST API is transitional",
        decision="Flask REST API is a transitional prototype",
        reason="Rapid MVP delivery",
        source="developer-Test",
        confidence="confirmed",
        project_id=project_id,
        tags=["pending_candidate"],
    )
    create_pending(
        tenant,
        user_id=user_id,
        project_id=project_id,
        candidates=[cand],
        source_text="We chose Flask for rapid MVP delivery; it is transitional.",
    )
    assert get_active_pending(tenant, user_id=user_id, project_id=project_id)

    result = asyncio.run(
        handle_pending_control_message(
            tenant,
            "yes",
            user_id=user_id,
            project_id=project_id,
            developer_name="Test User",
        )
    )
    assert result is not None
    assert result["handled"] is True
    assert result["intent"] == "confirm_all"
    assert result["ok"] is True
    assert "Saved" in (result.get("reply") or "")

    assert get_active_pending(tenant, user_id=user_id, project_id=project_id) is None

    stored = list_memories(tenant, confidence="confirmed")
    assert any("Flask" in (m.get("title") or "") for m in stored)


def test_yes_with_knowledge_replaces_question_title(sibyl_tmpdir: Path):
    """CRITICAL: 'yes, <knowledge>' must save knowledge — not the trigger question."""
    tenant = "acme/pending-know"
    user_id = "user-1"
    project_id = "proj-1"
    question = (
        "What technical decisions were driven by business requirements "
        "rather than purely technical reasons?"
    )
    # Bad pending candidate shaped like the historical bug
    cand = build_memory(
        memory_type="architectural_decision",
        title=question,
        decision=question,
        content=question,
        source="developer-Test",
        confidence="confirmed",
        project_id=project_id,
        trigger_question=question,
        tags=["pending_candidate", "gap_answer"],
    )
    create_pending(
        tenant,
        user_id=user_id,
        project_id=project_id,
        candidates=[cand],
        source_text=question,
        question=question,
        gap_memory_id="gap-1",
    )

    result = asyncio.run(
        handle_pending_control_message(
            tenant,
            "yes, the authorisation so i can have more users with normal keys "
            "and control them with master keys without oauth",
            user_id=user_id,
            project_id=project_id,
            developer_name="Test User",
        )
    )
    assert result is not None
    assert result["ok"] is True
    assert get_active_pending(tenant, user_id=user_id, project_id=project_id) is None

    stored = list_memories(tenant, confidence="confirmed")
    assert stored
    titles = [m.get("title") or "" for m in stored]
    assert not any(t.strip().lower() == question.lower() for t in titles)
    assert any("authorisation" in t.lower() or "authorization" in t.lower() or "normal keys" in t.lower() for t in titles)
    assert any(m.get("trigger_question") == question for m in stored)


def test_confirm_pending_clears_and_verifies(sibyl_tmpdir: Path):
    tenant = "acme/pending2"
    user_id = "u2"
    project_id = "p2"
    cand = build_memory(
        memory_type="constraint",
        title="Mobile-first vendor dashboard",
        decision="Vendor dashboard must be mobile-first",
        reason="Field operations",
        source="developer-Test",
        confidence="confirmed",
        project_id=project_id,
    )
    create_pending(
        tenant,
        user_id=user_id,
        project_id=project_id,
        candidates=[cand],
        source_text="Vendor dashboard must be mobile-first because of field ops.",
    )
    result = confirm_pending(
        tenant,
        user_id=user_id,
        project_id=project_id,
        developer_name="Test",
    )
    assert result["ok"] is True
    assert len(result["verified"]) >= 1
    assert get_active_pending(tenant, user_id=user_id, project_id=project_id) is None


def test_extract_never_uses_question_as_title(sibyl_tmpdir: Path):
    question = (
        "What technical decisions were driven by business requirements "
        "rather than purely technical reasons?"
    )
    answer = (
        "authorization so i can have more users with normal keys "
        "and control them with master keys without oauth"
    )
    with patch("app.services.teach.is_llm_configured", return_value=False):
        cands = asyncio.run(
            extract_candidate_memories(
                f"Trigger question (CONTEXT ONLY):\n{question}\n\n"
                f"Developer answer:\n{answer}",
                developer_name="Test",
                project_id="p1",
                question=question,
                answer_only=answer,
            )
        )
    assert cands
    assert cands[0]["title"].rstrip("?") != question.rstrip("?")
    assert not cands[0]["title"].endswith("?")
    assert cands[0].get("trigger_question") == question
    assert cands[0].get("candidate_id")


def test_teach_does_not_overwrite_title_with_question(sibyl_tmpdir: Path):
    tenant = "acme/teach-title"
    question = "What technical decisions were driven by business requirements?"
    answer = (
        "we use master keys and normal keys for authorization without oauth "
        "because we need many users quickly"
    )
    with patch("app.services.teach.is_llm_configured", return_value=False):
        result = asyncio.run(
            teach_kassandra(
                tenant,
                answer,
                developer_name="Test",
                project_id="proj-teach",
                user_id="u-teach",
                question=question,
                gap_memory_id="gap-x",
            )
        )
    assert result["awaiting_confirmation"] is True
    mem = result["memory"]
    assert mem is not None
    assert mem["title"].lower() != question.lower()
    assert "master" in (mem.get("title") or "").lower() or "normal" in (
        mem.get("title") or ""
    ).lower() or "authorization" in (mem.get("title") or "").lower() or "authorisation" in (
        mem.get("title") or ""
    ).lower()
    assert mem.get("trigger_question") == question


def test_duplicate_not_recreated(sibyl_tmpdir: Path):
    tenant = "acme/dup"
    project_id = "p-dup"
    mem = build_memory(
        memory_type="architectural_decision",
        title="Authorization uses master-key and normal-key model instead of OAuth",
        decision="Use master keys and normal keys instead of OAuth",
        reason="Support multiple users without OAuth",
        source="developer-Test",
        confidence="confirmed",
        project_id=project_id,
    )
    store_memory(tenant, mem)
    create_pending(
        tenant,
        user_id="u",
        project_id=project_id,
        candidates=[
            build_memory(
                memory_type="architectural_decision",
                title="Business requirements led to a master-key and normal-key authorization system",
                decision="Use master keys and normal keys instead of OAuth",
                reason="Support multiple users without OAuth",
                source="developer-Test",
                confidence="confirmed",
                project_id=project_id,
            )
        ],
        source_text="same knowledge again",
    )
    result = confirm_pending(
        tenant,
        user_id="u",
        project_id=project_id,
        developer_name="Test",
    )
    assert result["ok"] is True
    assert any(m.get("_duplicate") for m in result["stored"])
    confirmed = list_memories(tenant, confidence="confirmed")
    # Should not explode into many copies of the same fact
    assert len(confirmed) <= 2
