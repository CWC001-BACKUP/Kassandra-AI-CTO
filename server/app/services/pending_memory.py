"""Pending institutional-memory confirmation — Sibyl-backed candidate store.

YES / NO / EDIT are control actions on pending candidates.
They must NEVER be passed through memory extraction as institutional knowledge.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from app.services.institutional_memory import (
    build_memory,
    developer_source_label,
    resolve_knowledge_gap,
    store_memory,
)
from app.services.memory import get_memory_provider

logger = logging.getLogger(__name__)

PENDING_CATEGORY = "pending"
PENDING_TTL_HOURS = 24

ConfirmationIntent = Literal[
    "confirm_all",
    "reject",
    "select",
    "edit",
    "confirm_with_knowledge",
    "none",
]

_CONFIRM_PATTERNS = (
    r"^(yes|yeah|yep|yup|y)\b",
    r"\b(save (it|them|this|these)|store (it|them)|remember (it|this|them)|add (it|them))\b",
    r"\b(confirm(ed)?|correct|that'?s (right|correct)|looks good|do it)\b",
)

_REJECT_PATTERNS = (
    r"^(no|nope|nah)\b",
    r"\b(don'?t save|do not save|discard|reject|cancel|never ?mind|that'?s wrong|not correct)\b",
)

_SELECT_PATTERN = re.compile(
    r"(?:save|keep|confirm|only)?\s*(?:numbers?\s*)?(\d+(?:\s*(?:and|,|&)\s*\d+)+|"
    r"\d+)\s*(?:and\s*\d+)*(?:\s*only)?",
    re.IGNORECASE,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _pending_key(user_id: str, project_id: str) -> str:
    safe_user = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id)[:40]
    safe_proj = re.sub(r"[^a-zA-Z0-9_-]", "_", project_id)[:40]
    return f"{safe_user}__{safe_proj}"


def _ref_key(user_id: str, project_id: str) -> str:
    return f"pending_confirmation__{_pending_key(user_id, project_id)}"


def detect_confirmation_intent(text: str) -> tuple[ConfirmationIntent, list[int] | None]:
    """Classify control actions for an active pending confirmation."""
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^\w\s'?]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "none", None

    # Selection: "save 1 and 3" / "only 2"
    select_match = re.search(
        r"(?:save|keep|confirm|only)\s+(?:numbers?\s+)?((?:\d+\s*(?:and|,|&)\s*)*\d+)",
        cleaned,
    )
    if select_match:
        nums = [int(n) for n in re.findall(r"\d+", select_match.group(1))]
        # Convert to 0-based indices
        indices = sorted({n - 1 for n in nums if n >= 1})
        if indices:
            return "select", indices

    # Edit / correction: "yes, but …" or "yes — actually …"
    if re.match(r"^(yes|yeah|yep)\b.+\b(but|however|actually|except)\b", cleaned):
        return "edit", None
    if re.search(r"\b(change|correct that|update|modify)\b", cleaned) and len(cleaned.split()) > 4:
        return "edit", None

    if any(re.search(p, cleaned) for p in _REJECT_PATTERNS):
        # Short rejects only — avoid catching long engineering answers that mention "no"
        if len(cleaned.split()) <= 12:
            return "reject", None

    # "yes, <substantive knowledge>" — confirm + replace candidate content
    if re.match(r"^(yes|yeah|yep|yup)\b", cleaned) and len(cleaned.split()) > 12:
        if not re.search(r"\b(but|however|actually|except)\b", cleaned):
            return "confirm_with_knowledge", None

    if any(re.search(p, cleaned) for p in _CONFIRM_PATTERNS):
        if len(cleaned.split()) <= 12:
            return "confirm_all", None

    return "none", None


def get_active_pending(
    tenant_id: str,
    *,
    user_id: str,
    project_id: str,
) -> dict[str, Any] | None:
    provider = get_memory_provider(tenant_id)
    key = _pending_key(user_id, project_id)
    recalled = provider.recall(PENDING_CATEGORY, key)
    body: dict[str, Any] | None = None
    if isinstance(recalled, dict):
        if recalled.get("pending_id"):
            body = recalled
        elif isinstance(recalled.get("body"), dict):
            body = recalled["body"]

    if not body:
        raw = provider.get_reference(_ref_key(user_id, project_id))
        if isinstance(raw, dict):
            content = raw.get("body")
            if isinstance(content, str):
                try:
                    body = json.loads(content)
                except json.JSONDecodeError:
                    body = None
            elif isinstance(content, dict):
                body = content

    if not body or body.get("status") != "PENDING_CONFIRMATION":
        return None

    expires = body.get("expires_at")
    if expires:
        try:
            exp_dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
            if exp_dt < _now():
                clear_pending(tenant_id, user_id=user_id, project_id=project_id)
                return None
        except ValueError:
            pass

    return body


def clear_pending(tenant_id: str, *, user_id: str, project_id: str) -> None:
    provider = get_memory_provider(tenant_id)
    key = _pending_key(user_id, project_id)
    try:
        provider.forget(PENDING_CATEGORY, key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to forget pending %s: %s", key, exc)
    try:
        # Overwrite reference with empty closed marker
        provider.set_reference(
            _ref_key(user_id, project_id),
            json.dumps({"status": "CLOSED", "closed_at": _now().isoformat()}),
            metadata={"kind": "pending_closed"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to clear pending ref: %s", exc)


def create_pending(
    tenant_id: str,
    *,
    user_id: str,
    project_id: str,
    candidates: list[dict[str, Any]],
    source_text: str,
    source: str = "developer",
    session_id: str | None = None,
    gap_memory_id: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    """Store extracted candidates awaiting confirmation (not permanent Sibyl memory)."""
    now = _now()
    normalized: list[dict[str, Any]] = []
    for cand in candidates:
        c = dict(cand)
        c["candidate_id"] = c.get("candidate_id") or uuid4().hex
        c["status"] = "PENDING_CONFIRMATION"
        if question and not c.get("trigger_question"):
            c["trigger_question"] = question
            c["question"] = question
        normalized.append(c)
    pending = {
        "pending_id": uuid4().hex,
        "project_id": project_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "session_id": session_id,
        "status": "PENDING_CONFIRMATION",
        "source": source,
        "source_text": source_text[:4000],
        "source_reference": "Teach Kassandra" if not session_id else "conversation",
        "gap_memory_id": gap_memory_id,
        "question": question,
        "candidate_memories": normalized,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=PENDING_TTL_HOURS)).isoformat(),
        "conversation_context": None,
    }
    provider = get_memory_provider(tenant_id)
    key = _pending_key(user_id, project_id)
    provider.remember(PENDING_CATEGORY, key, pending)
    provider.set_reference(
        _ref_key(user_id, project_id),
        json.dumps(pending),
        metadata={"kind": "pending_confirmation", "pending_id": pending["pending_id"]},
    )
    return pending


def format_pending_prompt(pending: dict[str, Any]) -> str:
    candidates = pending.get("candidate_memories") or []
    lines = [
        "This sounds like useful institutional context.",
        "",
        f"I extracted {len(candidates)} potential memor"
        + ("y:" if len(candidates) == 1 else "ies:"),
        "",
    ]
    for i, mem in enumerate(candidates, start=1):
        title = mem.get("title") or mem.get("decision") or f"Memory {i}"
        # Never display a bare trigger question as if it were the knowledge
        trigger = (mem.get("trigger_question") or pending.get("question") or "").strip()
        if trigger and title.strip().lower() == trigger.lower():
            title = mem.get("decision") or "Developer-confirmed knowledge"
        reason = mem.get("reason")
        decision = mem.get("decision")
        lines.append(f"{i}. {title}")
        if decision and decision != title:
            lines.append(f"   Decision: {decision}")
        if reason:
            lines.append(f"   Reason: {reason}")
        if mem.get("_near_duplicate_of") or "possible_duplicate" in (mem.get("tags") or []):
            lines.append("   Note: similar knowledge may already exist in Sibyl.")
    lines.extend(
        [
            "",
            "Would you like me to save these to Sibyl?",
            "Reply yes to save all, no to discard, or e.g. \"save 1 and 3\".",
        ]
    )
    return "\n".join(lines)


def _verify_stored(tenant_id: str, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Read-back verification so we never claim a phantom save."""
    from app.services.institutional_memory import list_memories

    verified: list[dict[str, Any]] = []
    existing = list_memories(tenant_id)
    by_id = {str(m.get("memory_id")): m for m in existing if m.get("memory_id")}
    for mem in memories:
        mid = str(mem.get("memory_id") or "")
        found = by_id.get(mid)
        if found and found.get("confidence") == "confirmed":
            verified.append(found)
        elif found:
            verified.append(found)
    return verified


def confirm_pending(
    tenant_id: str,
    *,
    user_id: str,
    project_id: str,
    indices: list[int] | None = None,
    developer_name: str | None = None,
) -> dict[str, Any]:
    """Save pending candidates to permanent Sibyl memory and clear pending state."""
    from app.services.institutional_memory import find_conflicts

    pending = get_active_pending(tenant_id, user_id=user_id, project_id=project_id)
    if not pending:
        return {
            "ok": False,
            "reason": "No pending memory confirmation is active.",
            "stored": [],
            "verified": [],
            "conflicts": [],
            "gaps_removed": 0,
        }

    candidates: list[dict[str, Any]] = list(pending.get("candidate_memories") or [])
    if indices is not None:
        selected = [candidates[i] for i in indices if 0 <= i < len(candidates)]
    else:
        selected = candidates

    if not selected:
        return {
            "ok": False,
            "reason": "No matching candidates to save.",
            "stored": [],
            "verified": [],
            "conflicts": [],
            "gaps_removed": 0,
        }

    developer_label = developer_source_label(developer_name)
    trigger = pending.get("question")
    stored: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for cand in selected:
        title = str(cand.get("title") or "").strip()
        decision = str(cand.get("decision") or "").strip()
        # Guard: never persist the trigger question as the knowledge title
        if trigger and title.lower() == str(trigger).strip().lower():
            title = decision or "Developer-confirmed knowledge"
        if title.endswith("?") and decision:
            title = decision[:160]

        mem = {
            **cand,
            "title": title,
            "decision": decision or title,
            "source": developer_label,
            "confidence": "confirmed",
            "evidence_type": "CONFIRMED",
            "status": "VERIFIED",
            "confirmed_at": _now().isoformat(),
            "project_id": project_id,
            "trigger_question": cand.get("trigger_question") or trigger,
            "question": cand.get("trigger_question") or trigger,
        }
        if not mem.get("memory_id"):
            built = build_memory(
                memory_type=mem.get("type") or "architectural_decision",
                title=str(mem.get("title") or "Confirmed knowledge"),
                content=mem.get("content"),
                decision=mem.get("decision"),
                reason=mem.get("reason"),
                context=mem.get("context"),
                alternatives=list(mem.get("alternatives") or []),
                outcome=mem.get("outcome"),
                source=developer_label,
                source_reference=pending.get("source_reference") or "Teach Kassandra",
                confidence="confirmed",
                evidence_type="CONFIRMED",
                project_id=project_id,
                affected_components=list(mem.get("affected_components") or []),
                trigger_question=mem.get("trigger_question"),
                question=mem.get("trigger_question"),
                status=mem.get("status")
                if mem.get("status") == "INTENTIONAL_TECH_DEBT"
                else "VERIFIED",
                lifecycle=mem.get("lifecycle") or "CURRENT",
                tags=list(mem.get("tags") or []) + ["teach_kassandra", "human_confirmed"],
            )
            mem = {**built, **{k: v for k, v in mem.items() if v is not None}}
            mem["status"] = (
                "INTENTIONAL_TECH_DEBT"
                if built.get("status") == "INTENTIONAL_TECH_DEBT"
                else "VERIFIED"
            )
        else:
            mem["status"] = (
                "INTENTIONAL_TECH_DEBT"
                if mem.get("status") == "INTENTIONAL_TECH_DEBT"
                else "VERIFIED"
            )
            mem["confirmed_at"] = _now().isoformat()
            mem["confidence"] = "confirmed"
            mem["evidence_type"] = "CONFIRMED"
            mem["source"] = developer_label
            # Refresh fingerprint from knowledge fields
            from app.services.institutional_memory import _fingerprint

            mem["fingerprint"] = _fingerprint(
                str(mem.get("title") or ""),
                mem.get("decision"),
                mem.get("content"),
                mem.get("reason"),
            )

        conflicts.extend(find_conflicts(tenant_id, mem))
        saved = store_memory(tenant_id, mem, skip_duplicate_check=False)
        if not saved.get("_duplicate"):
            stored.append(saved)
        else:
            # Duplicate of confirmed memory still counts as present — do not re-create
            stored.append({**saved, "_duplicate": True})

    verified = _verify_stored(tenant_id, [m for m in stored if not m.get("_duplicate")])
    for m in stored:
        if m.get("_duplicate"):
            verified.append(m)

    gaps_removed = 0
    if pending.get("gap_memory_id") or pending.get("question"):
        gaps_removed = resolve_knowledge_gap(
            tenant_id,
            memory_id=pending.get("gap_memory_id"),
            question=pending.get("question"),
        )
        if gaps_removed == 0:
            logger.warning(
                "Pending confirmed but knowledge gap not removed (id=%s question=%r)",
                pending.get("gap_memory_id"),
                pending.get("question"),
            )

    # Always clear pending after a successful store attempt so confirmation does not loop
    clear_pending(tenant_id, user_id=user_id, project_id=project_id)

    ok = len(verified) >= 1
    titles = [str(m.get("title") or m.get("decision") or "Memory") for m in stored]
    conflict_note = ""
    if conflicts:
        conflict_note = (
            "\n\nNote: this may conflict with existing institutional memory:\n"
            + "\n".join(
                f"• {c.get('title') or c.get('decision')}" for c in conflicts[:3]
            )
        )

    if not ok:
        return {
            "ok": False,
            "reason": "Storage verification failed — nothing confirmed in Sibyl.",
            "stored": stored,
            "verified": verified,
            "conflicts": conflicts,
            "gaps_removed": gaps_removed,
            "reply": "I could not verify the save in Sibyl. Nothing was confirmed.",
        }

    new_count = sum(1 for m in stored if not m.get("_duplicate"))
    dup_count = sum(1 for m in stored if m.get("_duplicate"))
    bullet = "\n".join(f"• {t}" for t in titles)
    if new_count and not dup_count:
        reply = (
            f"Saved {new_count} institutional memor"
            f"{'y' if new_count == 1 else 'ies'} to Sibyl:\n\n{bullet}"
        )
    elif dup_count and not new_count:
        reply = (
            "That knowledge already exists in Sibyl — I did not create a duplicate:\n\n"
            f"{bullet}"
        )
    else:
        reply = (
            f"Saved {new_count} new memor{'y' if new_count == 1 else 'ies'} "
            f"and matched {dup_count} existing entr{'y' if dup_count == 1 else 'ies'}:\n\n"
            f"{bullet}"
        )
    reply += conflict_note
    return {
        "ok": True,
        "reason": None,
        "stored": stored,
        "verified": verified,
        "conflicts": conflicts,
        "reply": reply,
        "gaps_removed": gaps_removed,
    }


def reject_pending(
    tenant_id: str,
    *,
    user_id: str,
    project_id: str,
) -> dict[str, Any]:
    pending = get_active_pending(tenant_id, user_id=user_id, project_id=project_id)
    if not pending:
        return {"ok": False, "reason": "No pending memory to discard.", "reply": None}
    clear_pending(tenant_id, user_id=user_id, project_id=project_id)
    return {
        "ok": True,
        "reason": None,
        "reply": "Discarded the pending institutional memories. Nothing was saved to Sibyl.",
    }


def _title_from_knowledge(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(
        r"^(yes|yeah|yep|yup|ok|okay)[,.\s]+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    first = cleaned.split(".")[0].strip() or cleaned
    first = first.split("\n")[0].strip()
    if first.endswith("?"):
        return "Developer-confirmed knowledge"
    return (first[:120] or "Developer-confirmed knowledge")


def _knowledge_after_yes(message: str) -> str:
    """Strip leading confirmation filler so remaining text is institutional knowledge."""
    cleaned = message.strip()
    cleaned = re.sub(
        r"^(yes|yeah|yep|yup|ok|okay|sure)[,.\s:\-—–]+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned or message.strip()


def _apply_knowledge_to_pending(
    pending: dict[str, Any],
    knowledge: str,
    *,
    developer_label: str,
) -> dict[str, Any]:
    """Replace question-shaped candidate titles with knowledge from the developer."""
    candidates = list(pending.get("candidate_memories") or [])
    trigger = (pending.get("question") or "").strip()
    title = _title_from_knowledge(knowledge)
    reason = None
    because = re.search(r"\bbecause\b(.+)", knowledge, re.IGNORECASE | re.DOTALL)
    if because:
        reason = because.group(1).strip()[:400]

    if not candidates:
        built = build_memory(
            memory_type="architectural_decision",
            title=title,
            content=knowledge[:2000],
            decision=title,
            reason=reason,
            source=developer_label,
            source_reference=pending.get("source_reference") or "Teach Kassandra",
            confidence="confirmed",
            evidence_type="CONFIRMED",
            project_id=pending.get("project_id"),
            trigger_question=trigger or None,
            question=trigger or None,
            tags=["teach_kassandra", "human_confirmed", "pending_candidate"],
        )
        built["candidate_id"] = uuid4().hex
        built["status"] = "PENDING_CONFIRMATION"
        candidates = [built]
    else:
        first = dict(candidates[0])
        old_title = str(first.get("title") or "")
        if (
            not old_title
            or old_title.endswith("?")
            or (trigger and old_title.lower() == trigger.lower())
            or old_title.lower() in {"developer-confirmed knowledge"}
        ):
            first["title"] = title
            first["decision"] = title
        else:
            first["decision"] = first.get("decision") or title
        first["content"] = knowledge[:2000]
        if reason:
            first["reason"] = reason
        if trigger:
            first["trigger_question"] = trigger
            first["question"] = trigger
            first["context"] = first.get("context") or f"Answered knowledge gap: {trigger}"
        first["source"] = developer_label
        first["confidence"] = "confirmed"
        first["evidence_type"] = "CONFIRMED"
        first["status"] = "PENDING_CONFIRMATION"
        from app.services.institutional_memory import _fingerprint

        first["fingerprint"] = _fingerprint(
            str(first.get("title") or ""),
            first.get("decision"),
            first.get("content"),
            first.get("reason"),
        )
        candidates[0] = first

    pending["candidate_memories"] = candidates
    pending["source_text"] = knowledge[:4000]
    pending["updated_at"] = _now().isoformat()
    pending["status"] = "PENDING_CONFIRMATION"

    provider = get_memory_provider(pending["tenant_id"])
    key = _pending_key(pending["user_id"], pending["project_id"])
    provider.remember(PENDING_CATEGORY, key, pending)
    provider.set_reference(
        _ref_key(pending["user_id"], pending["project_id"]),
        json.dumps(pending),
        metadata={"kind": "pending_confirmation", "pending_id": pending["pending_id"]},
    )
    return pending


def update_pending_with_correction(
    tenant_id: str,
    *,
    user_id: str,
    project_id: str,
    correction_text: str,
    developer_name: str | None,
) -> dict[str, Any]:
    """Merge a user correction into pending candidates and keep PENDING_CONFIRMATION."""
    pending = get_active_pending(tenant_id, user_id=user_id, project_id=project_id)
    if not pending:
        return {"ok": False, "reason": "No pending memory to update.", "pending": None}

    developer_label = developer_source_label(developer_name)
    knowledge = _knowledge_after_yes(correction_text)
    pending = _apply_knowledge_to_pending(
        pending,
        knowledge,
        developer_label=developer_label,
    )

    return {
        "ok": True,
        "pending": pending,
        "reply": format_pending_prompt(pending)
        + "\n\nI updated the candidate with your correction. Confirm to save to Sibyl?",
    }


async def handle_pending_control_message(
    tenant_id: str,
    message: str,
    *,
    user_id: str,
    project_id: str,
    developer_name: str | None,
) -> dict[str, Any] | None:
    """If pending confirmation is active, handle yes/no/select/edit. Else return None."""
    pending = get_active_pending(tenant_id, user_id=user_id, project_id=project_id)
    if not pending:
        return None

    intent, indices = detect_confirmation_intent(message)
    if intent == "confirm_with_knowledge":
        developer_label = developer_source_label(developer_name)
        knowledge = _knowledge_after_yes(message)
        _apply_knowledge_to_pending(
            pending,
            knowledge,
            developer_label=developer_label,
        )
        result = confirm_pending(
            tenant_id,
            user_id=user_id,
            project_id=project_id,
            developer_name=developer_name,
        )
        return {
            "handled": True,
            "intent": "confirm_all",
            **result,
        }
    if intent == "confirm_all":
        result = confirm_pending(
            tenant_id,
            user_id=user_id,
            project_id=project_id,
            developer_name=developer_name,
        )
        return {
            "handled": True,
            "intent": "confirm_all",
            **result,
        }
    if intent == "select" and indices is not None:
        result = confirm_pending(
            tenant_id,
            user_id=user_id,
            project_id=project_id,
            indices=indices,
            developer_name=developer_name,
        )
        return {"handled": True, "intent": "select", **result}
    if intent == "reject":
        result = reject_pending(tenant_id, user_id=user_id, project_id=project_id)
        return {"handled": True, "intent": "reject", **result}
    if intent == "edit":
        result = update_pending_with_correction(
            tenant_id,
            user_id=user_id,
            project_id=project_id,
            correction_text=message,
            developer_name=developer_name,
        )
        return {"handled": True, "intent": "edit", **result}

    # Pending exists but message is not a control action — remind user
    # Only intercept very short ambiguous messages that look like failed confirms
    if len(message.strip().split()) <= 3 and message.strip().lower() in {
        "ok",
        "sure",
        "please",
        "go ahead",
    }:
        result = confirm_pending(
            tenant_id,
            user_id=user_id,
            project_id=project_id,
            developer_name=developer_name,
        )
        return {"handled": True, "intent": "confirm_all", **result}

    return {
        "handled": True,
        "intent": "remind",
        "ok": True,
        "reply": (
            "You still have pending institutional memories waiting for confirmation.\n\n"
            + format_pending_prompt(pending)
        ),
        "pending": pending,
        # Don't block long engineering questions — only remind for short msgs
        "block": len(message.strip().split()) <= 8,
    }
