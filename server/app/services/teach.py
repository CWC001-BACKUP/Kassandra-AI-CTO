"""Teach Kassandra — extract candidates, then confirm into Sibyl.

Confirmation responses (yes/no) are control actions handled by pending_memory.
They must never be run through institutional-memory extraction.

Permanent memories store KNOWLEDGE from the developer answer — never the
trigger question as the title.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import uuid4

from app.services.institutional_memory import (
    build_memory,
    developer_source_label,
    find_conflicts,
    find_duplicate,
)
from app.services.llm import LLMError, chat_completion, is_llm_configured
from app.services.pending_memory import (
    confirm_pending,
    create_pending,
    format_pending_prompt,
    get_active_pending,
    handle_pending_control_message,
    reject_pending,
)

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """Extract one or more structured institutional engineering memories from the developer statement.

The developer answer is the knowledge. Any "trigger question" or "knowledge gap" text is CONTEXT ONLY — never use it as the memory title or decision.

Return ONLY valid JSON (no markdown) with this shape:
{
  "memories": [
    {
      "type": "architectural_decision" | "historical_event" | "constraint" | "incident" | "observation",
      "title": "short factual title of the KNOWLEDGE (never a question)",
      "decision": "what was decided or what is true",
      "reason": "why, if stated",
      "context": "optional surrounding context",
      "alternatives": ["..."],
      "outcome": "result if stated",
      "affected_components": ["database", "auth", "..."],
      "tags": ["..."],
      "lifecycle": "CURRENT" | "HISTORICAL" | "PLANNED" | "DEPRECATED" | "UNKNOWN",
      "status": "ACTIVE" | "INTENTIONAL_TECH_DEBT",
      "historical_date": "ISO date or null"
    }
  ]
}

Rules:
- Only extract what the developer actually said. Do not invent history.
- Title and decision must state the knowledge (e.g. "Authorization uses master-key and normal-key model instead of OAuth"), NEVER the question that prompted them.
- Distinguish INTENT (what the developer says the system should do) from IMPLEMENTATION claims — only record what they stated.
- If they mark something as intentional technical debt, set status to INTENTIONAL_TECH_DEBT.
- Split distinct facts into separate memories when appropriate.
- If nothing institutional is present, return {"memories": []}.
"""

_CANDIDATE_HINTS = (
    r"\bwe (originally|used to|tried|migrated|switched|chose|decided|abandoned)\b",
    r"\bbecause\b",
    r"\b(reason|rationale|trade-?off|incident|outage|postmortem)\b",
    r"\b(instead of|rather than|replaced)\b",
    r"\blegacy\b",
    r"\b(intentional|transitional|temporary|mvp)\b",
    r"\b(authori[sz]ation|auth|oauth|master[- ]?key|normal[- ]?key)\b",
)


def looks_like_institutional_statement(text: str) -> bool:
    lower = text.strip().lower()
    if len(lower.split()) < 8:
        return False
    return any(re.search(p, lower) for p in _CANDIDATE_HINTS)


def candidate_confirmation_prompt(text: str) -> str | None:
    """Legacy helper — chat now uses pending_memory prompts."""
    if not looks_like_institutional_statement(text):
        return None
    return (
        "This sounds like useful historical context. "
        "I will extract candidate memories for your confirmation before saving to Sibyl."
    )


def _title_from_answer(text: str) -> str:
    """Derive a knowledge title from the answer body — never prefer a question."""
    cleaned = text.strip()
    # Prefer clause after leading yes/confirm filler
    cleaned = re.sub(
        r"^(yes|yeah|yep|yup|ok|okay)[,.\s]+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    first = cleaned.split(".")[0].strip() or cleaned
    first = first.split("\n")[0].strip()
    if first.endswith("?"):
        # Still a question — fall back to a generic knowledge label
        return "Developer-confirmed knowledge"
    return (first[:120] or "Developer-confirmed knowledge")


def _compose_extract_user_payload(
    *,
    answer: str,
    question: str | None,
    extra: str | None,
) -> str:
    """Build LLM input: answer is knowledge; question is metadata only."""
    parts: list[str] = []
    if question and question.strip():
        parts.append(
            "Trigger question (CONTEXT ONLY — do not use as title or decision):\n"
            f"{question.strip()}"
        )
    parts.append(f"Developer answer (this is the institutional knowledge):\n{answer.strip()}")
    if extra and extra.strip():
        parts.append(f"Additional context:\n{extra.strip()}")
    return "\n\n".join(parts)


def _attach_candidate_ids(
    memories: list[dict[str, Any]],
    *,
    question: str | None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for mem in memories:
        m = dict(mem)
        m["candidate_id"] = m.get("candidate_id") or uuid4().hex
        if question:
            m["trigger_question"] = question.strip()
            m["question"] = question.strip()
            tags = list(m.get("tags") or [])
            if "gap_answer" not in tags:
                tags.append("gap_answer")
            m["tags"] = tags
            if not m.get("context"):
                m["context"] = f"Answered knowledge gap: {question.strip()[:300]}"
        m["status"] = "PENDING_CONFIRMATION"
        m["evidence_type"] = m.get("evidence_type") or "CONFIRMED"
        out.append(m)
    return out


def _heuristic_candidates(
    text: str,
    *,
    developer_label: str,
    project_id: str | None,
    question: str | None = None,
) -> list[dict[str, Any]]:
    title = _title_from_answer(text)
    reason = None
    because = re.search(r"\bbecause\b(.+)", text, re.IGNORECASE | re.DOTALL)
    if because:
        reason = because.group(1).strip()[:400]
    status = "ACTIVE"
    if re.search(r"\bintentional\b.*\b(debt|tech)\b|\btech(?:nical)? debt\b", text, re.I):
        status = "INTENTIONAL_TECH_DEBT"
    mem = build_memory(
        memory_type="architectural_decision",
        title=title,
        content=text.strip()[:2000],
        decision=title,
        reason=reason,
        context=(f"Answered knowledge gap: {question}" if question else None),
        source=developer_label,
        source_reference="Teach Kassandra",
        confidence="confirmed",
        evidence_type="CONFIRMED",
        project_id=project_id,
        trigger_question=question,
        question=question,
        status=status,
        tags=["teach_kassandra", "human_confirmed", "pending_candidate"],
    )
    mem["status"] = "PENDING_CONFIRMATION"
    return [mem]


async def extract_candidate_memories(
    text: str,
    *,
    developer_name: str | None,
    project_id: str | None,
    question: str | None = None,
    answer_only: str | None = None,
) -> list[dict[str, Any]]:
    developer_label = developer_source_label(developer_name)
    allowed = {
        "architectural_decision",
        "historical_event",
        "constraint",
        "incident",
        "observation",
    }
    knowledge_text = (answer_only or text).strip()

    if is_llm_configured():
        try:
            raw = await chat_completion(
                [
                    {"role": "system", "content": _EXTRACT_PROMPT},
                    {"role": "user", "content": text.strip()},
                ]
            )
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            items = data.get("memories") if isinstance(data, dict) else None
            if items is None and isinstance(data, dict) and data.get("type"):
                items = [data]
            if not isinstance(items, list):
                items = []
            memories: list[dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict) or not item.get("type"):
                    continue
                raw_type = str(item.get("type") or "architectural_decision")
                mem_type = raw_type if raw_type in allowed else "architectural_decision"
                decision = str(item.get("decision") or "").strip()
                raw_title = str(item.get("title") or "").strip()
                # Never fall back to the trigger question
                if not raw_title or raw_title.endswith("?"):
                    raw_title = decision or _title_from_answer(knowledge_text)
                if question and raw_title.strip().lower() == question.strip().lower():
                    raw_title = decision or _title_from_answer(knowledge_text)
                title = raw_title[:160] or "Developer-confirmed knowledge"
                life = item.get("lifecycle") or "CURRENT"
                status = item.get("status") or "ACTIVE"
                mem = build_memory(
                    memory_type=mem_type,  # type: ignore[arg-type]
                    title=title,
                    content=knowledge_text[:2000],
                    decision=decision or title,
                    reason=item.get("reason"),
                    context=item.get("context")
                    or (f"Answered knowledge gap: {question}" if question else None),
                    alternatives=list(item.get("alternatives") or []),
                    outcome=item.get("outcome"),
                    source=developer_label,
                    source_reference="Teach Kassandra",
                    confidence="confirmed",
                    evidence_type="CONFIRMED",
                    project_id=project_id,
                    historical_date=item.get("historical_date"),
                    affected_components=list(item.get("affected_components") or []),
                    trigger_question=question,
                    question=question,
                    status=status if status == "INTENTIONAL_TECH_DEBT" else "ACTIVE",
                    lifecycle=life if life in {"CURRENT", "HISTORICAL", "PLANNED", "DEPRECATED", "UNKNOWN"} else "CURRENT",
                    tags=list(item.get("tags") or [])
                    + ["teach_kassandra", "human_confirmed", "pending_candidate"],
                )
                mem["status"] = "PENDING_CONFIRMATION"
                memories.append(mem)
            if memories:
                return _attach_candidate_ids(memories, question=question)
        except (LLMError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Teach extract via LLM failed, using heuristic: %s", exc)

    return _attach_candidate_ids(
        _heuristic_candidates(
            knowledge_text,
            developer_label=developer_label,
            project_id=project_id,
            question=question,
        ),
        question=question,
    )


def _pending_response_from_control(control: dict[str, Any]) -> dict[str, Any]:
    stored_list = control.get("stored") or []
    intent = control.get("intent")
    saved = bool(control.get("ok")) and intent in {"confirm_all", "select"}
    return {
        "stored": saved,
        "awaiting_confirmation": intent in {"edit", "remind"},
        "reason": control.get("reason"),
        "memory": stored_list[0] if stored_list else None,
        "memories": stored_list,
        "pending": control.get("pending"),
        "conflicts": control.get("conflicts") or [],
        "gap_resolved": bool(control.get("gaps_removed")),
        "gaps_removed": control.get("gaps_removed") or 0,
        "reply": control.get("reply"),
        "verified": saved,
        "duplicate": any(m.get("_duplicate") for m in stored_list),
    }


async def teach_kassandra(
    tenant_id: str,
    text: str,
    *,
    developer_name: str | None,
    project_id: str | None,
    user_id: str | None = None,
    gap_memory_id: str | None = None,
    question: str | None = None,
    extra: str | None = None,
    session_id: str | None = None,
    confirm: bool | None = None,
    pending_id: str | None = None,
    selected_indices: list[int] | None = None,
) -> dict[str, Any]:
    """Extract candidates into pending state, or confirm/reject pending.

    - Default: extract → PENDING_CONFIRMATION (not permanent Sibyl yet)
    - confirm=True: save active pending to Sibyl (YES control action)
    - confirm=False: discard pending
    - selected_indices: 0-based subset to save when confirming (others discarded)
    - While pending is active: NEVER run normal extraction on control text
    """
    if not project_id or not user_id:
        return {
            "stored": False,
            "awaiting_confirmation": False,
            "reason": "Active project and user are required.",
            "memory": None,
            "memories": [],
            "pending": None,
            "conflicts": [],
            "gap_resolved": False,
            "gaps_removed": 0,
        }

    # Control actions on existing pending — NEVER extract "yes"/"no"
    if confirm is True or (pending_id and confirm is not False and selected_indices is not None):
        pending_before = get_active_pending(tenant_id, user_id=user_id, project_id=project_id)
        total = len((pending_before or {}).get("candidate_memories") or [])
        result = confirm_pending(
            tenant_id,
            user_id=user_id,
            project_id=project_id,
            indices=selected_indices,
            developer_name=developer_name,
        )
        stored_list = result.get("stored") or []
        selected_count = len(stored_list)
        discarded_count = max(0, total - selected_count) if selected_indices is not None else 0
        reply = result.get("reply")
        if result.get("ok") and selected_indices is not None and discarded_count:
            reply = (
                f"{reply}\n\nSaved {selected_count}, discarded {discarded_count}."
                if reply
                else f"Saved {selected_count}, discarded {discarded_count}."
            )
        return {
            "stored": bool(result.get("ok")),
            "awaiting_confirmation": False,
            "reason": result.get("reason"),
            "memory": stored_list[0] if stored_list else None,
            "memories": stored_list,
            "pending": None,
            "conflicts": result.get("conflicts") or [],
            "duplicate": any(m.get("_duplicate") for m in stored_list),
            "gap_resolved": bool(result.get("gaps_removed")),
            "gaps_removed": result.get("gaps_removed") or 0,
            "reply": reply,
            "verified": bool(result.get("ok")),
            "selected_count": selected_count if result.get("ok") else 0,
            "discarded_count": discarded_count if result.get("ok") else 0,
        }

    if confirm is False:
        result = reject_pending(tenant_id, user_id=user_id, project_id=project_id)
        return {
            "stored": False,
            "awaiting_confirmation": False,
            "reason": result.get("reason"),
            "memory": None,
            "memories": [],
            "pending": None,
            "conflicts": [],
            "gap_resolved": False,
            "gaps_removed": 0,
            "reply": result.get("reply"),
        }

    # If user sent a confirmation string while pending exists, handle as control
    control = await handle_pending_control_message(
        tenant_id,
        text,
        user_id=user_id,
        project_id=project_id,
        developer_name=developer_name,
    )
    if control and control.get("handled"):
        # Active pending: never fall through to extraction (including remind)
        return _pending_response_from_control(control)

    answer = text.strip()
    if len(answer) < 8 and not (question and answer):
        return {
            "stored": False,
            "awaiting_confirmation": False,
            "reason": "Answer is too short — add a bit more detail.",
            "memory": None,
            "memories": [],
            "pending": None,
            "conflicts": [],
            "gap_resolved": False,
            "gaps_removed": 0,
        }

    payload = _compose_extract_user_payload(
        answer=answer,
        question=question,
        extra=extra,
    )
    if len(answer) < 8:
        return {
            "stored": False,
            "awaiting_confirmation": False,
            "reason": "Answer is too short — add a bit more detail.",
            "memory": None,
            "memories": [],
            "pending": None,
            "conflicts": [],
            "gap_resolved": False,
            "gaps_removed": 0,
        }

    candidates = await extract_candidate_memories(
        payload,
        developer_name=developer_name,
        project_id=project_id,
        question=question,
        answer_only=answer if not extra else f"{answer}\n\n{extra}".strip(),
    )
    if not candidates:
        return {
            "stored": False,
            "awaiting_confirmation": False,
            "reason": "No institutional knowledge could be extracted from that statement.",
            "memory": None,
            "memories": [],
            "pending": None,
            "conflicts": [],
            "gap_resolved": False,
            "gaps_removed": 0,
        }

    # Surface near-duplicates / conflicts before confirmation
    conflicts: list[dict[str, Any]] = []
    for cand in candidates:
        dup = find_duplicate(tenant_id, cand)
        if dup and not dup.get("_duplicate"):
            cand["_near_duplicate_of"] = dup.get("memory_id")
            cand["tags"] = list(cand.get("tags") or []) + ["possible_duplicate"]
        conflicts.extend(find_conflicts(tenant_id, cand))

    pending = create_pending(
        tenant_id,
        user_id=user_id,
        project_id=project_id,
        candidates=candidates,
        source_text=answer[:4000],
        source=developer_source_label(developer_name),
        session_id=session_id,
        gap_memory_id=gap_memory_id,
        question=question,
    )

    return {
        "stored": False,
        "awaiting_confirmation": True,
        "reason": None,
        "memory": candidates[0],
        "memories": candidates,
        "pending": {
            "pending_id": pending["pending_id"],
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "index": i,
                    "candidate_id": c.get("candidate_id"),
                    "title": c.get("title"),
                    "decision": c.get("decision"),
                    "reason": c.get("reason"),
                    "content": c.get("content"),
                    "context": c.get("context"),
                    "type": c.get("type"),
                    "confidence": "confirmed",
                    "evidence_type": "CONFIRMED",
                    "status": "PENDING_CONFIRMATION",
                    "trigger_question": c.get("trigger_question") or question,
                    "possible_duplicate": bool(c.get("_near_duplicate_of")),
                }
                for i, c in enumerate(candidates)
            ],
        },
        "conflicts": [
            {"memory_id": c.get("memory_id"), "title": c.get("title"), "decision": c.get("decision")}
            for c in conflicts[:5]
        ],
        "gap_resolved": False,
        "gaps_removed": 0,
        "reply": format_pending_prompt(pending),
        "verified": False,
    }


async def process_teach_control_or_extract(
    tenant_id: str,
    message: str,
    *,
    user_id: str,
    project_id: str,
    developer_name: str | None,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Chat entry: handle pending confirmation first; else extract institutional statements."""
    # Hard gate: any active pending is handled before extraction — never extract "yes"
    control = await handle_pending_control_message(
        tenant_id,
        message,
        user_id=user_id,
        project_id=project_id,
        developer_name=developer_name,
    )
    if control and control.get("handled"):
        if control.get("intent") == "remind" and not control.get("block"):
            # Pending exists but user asked a long engineering question —
            # remind without treating their message as new memory extraction.
            return {
                **control,
                "reply": (
                    (control.get("reply") or "")
                    + "\n\n(Your question will still be answered; "
                    "confirm or discard the pending memories when ready.)"
                ),
                "passthrough_chat": True,
            }
        return control

    if looks_like_institutional_statement(message):
        return await teach_kassandra(
            tenant_id,
            message,
            developer_name=developer_name,
            project_id=project_id,
            user_id=user_id,
            session_id=session_id,
        )

    return None
