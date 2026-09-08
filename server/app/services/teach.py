"""Teach Kassandra — human knowledge ingestion into Sibyl institutional memory."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.institutional_memory import (
    SOURCE_CONVERSATION,
    build_memory,
    developer_source_label,
    find_conflicts,
    find_duplicate,
    resolve_knowledge_gap,
    store_memory,
)
from app.services.llm import LLMError, chat_completion, is_llm_configured

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """Extract structured institutional engineering memory from the developer statement.

Return ONLY valid JSON (no markdown) with this shape:
{
  "type": "architectural_decision" | "historical_event" | "constraint" | "incident" | "observation",
  "title": "short title",
  "decision": "what was decided or what happened",
  "reason": "why, if stated",
  "alternatives": ["..."],
  "outcome": "result if stated",
  "affected_components": ["database", "auth", "..."],
  "tags": ["..."],
  "historical_date": "ISO date or null"
}

Rules:
- Only extract what the developer actually said. Do not invent history.
- If nothing institutional is present, return {"type": null}.
"""

_CANDIDATE_HINTS = (
    r"\bwe (originally|used to|tried|migrated|switched|chose|decided|abandoned)\b",
    r"\bbecause\b",
    r"\b(reason|rationale|trade-?off|incident|outage|postmortem)\b",
    r"\b(instead of|rather than|replaced)\b",
    r"\blegacy\b",
)


def looks_like_institutional_statement(text: str) -> bool:
    lower = text.strip().lower()
    if len(lower.split()) < 8:
        return False
    return any(re.search(p, lower) for p in _CANDIDATE_HINTS)


def _compose_gap_answer(
    *,
    question: str,
    answer: str,
    extra: str | None,
) -> str:
    parts = [
        f"Knowledge gap answered: {question.strip()}",
        f"Developer answer: {answer.strip()}",
    ]
    if extra and extra.strip():
        parts.append(f"Additional context: {extra.strip()}")
    return "\n\n".join(parts)


def _heuristic_extract(
    text: str,
    *,
    developer_label: str,
    project_id: str | None,
) -> dict[str, Any]:
    """Fallback extractor when LLM is unavailable."""
    title = text.strip().split(".")[0][:120] or "Developer-confirmed knowledge"
    reason = None
    because = re.search(r"\bbecause\b(.+)", text, re.IGNORECASE | re.DOTALL)
    if because:
        reason = because.group(1).strip()[:400]
    return build_memory(
        memory_type="architectural_decision",
        title=title,
        content=text.strip()[:2000],
        decision=title,
        reason=reason,
        source=developer_label,
        source_reference="Teach Kassandra",
        confidence="confirmed",
        project_id=project_id,
        tags=["teach_kassandra", "human_confirmed"],
    )


async def extract_memory_from_teaching(
    text: str,
    *,
    developer_name: str | None,
    project_id: str | None,
    question: str | None = None,
) -> dict[str, Any] | None:
    """Use LLM (or heuristic) to structure a Teach Kassandra statement."""
    developer_label = developer_source_label(developer_name)

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
            if not data.get("type"):
                return None
            raw_type = str(data.get("type") or "architectural_decision")
            allowed = {
                "architectural_decision",
                "historical_event",
                "constraint",
                "incident",
                "observation",
            }
            mem_type = raw_type if raw_type in allowed else "architectural_decision"
            title = str(data.get("title") or question or "Developer-confirmed knowledge")[:160]
            return build_memory(
                memory_type=mem_type,  # type: ignore[arg-type]
                title=title,
                content=text.strip()[:2000],
                decision=data.get("decision") or title,
                reason=data.get("reason"),
                alternatives=list(data.get("alternatives") or []),
                outcome=data.get("outcome"),
                source=developer_label,
                source_reference="Teach Kassandra",
                confidence="confirmed",
                project_id=project_id,
                historical_date=data.get("historical_date"),
                affected_components=list(data.get("affected_components") or []),
                tags=list(data.get("tags") or []) + ["teach_kassandra", "human_confirmed"],
            )
        except (LLMError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Teach extract via LLM failed, using heuristic: %s", exc)

    mem = _heuristic_extract(text, developer_label=developer_label, project_id=project_id)
    if question:
        mem["title"] = question[:160]
        mem["decision"] = mem.get("decision") or question[:200]
    return mem


async def teach_kassandra(
    tenant_id: str,
    text: str,
    *,
    developer_name: str | None,
    project_id: str | None,
    gap_memory_id: str | None = None,
    question: str | None = None,
    extra: str | None = None,
) -> dict[str, Any]:
    """Extract + store confirmed institutional memory via Sibyl.

    When answering a knowledge gap, ``text`` is the answer; optional ``extra``
    is additional free-form context. The gap is removed from Sibyl after save.
    """
    payload = text.strip()
    if question:
        payload = _compose_gap_answer(question=question, answer=payload, extra=extra)
    elif extra and extra.strip():
        payload = f"{payload}\n\nAdditional context: {extra.strip()}"

    if len(payload) < 8:
        return {
            "stored": False,
            "reason": "Answer is too short — add a bit more detail.",
            "memory": None,
            "conflicts": [],
            "gap_resolved": False,
            "gaps_removed": 0,
        }

    memory = await extract_memory_from_teaching(
        payload,
        developer_name=developer_name,
        project_id=project_id,
        question=question,
    )
    if not memory:
        return {
            "stored": False,
            "reason": "No institutional knowledge could be extracted from that statement.",
            "memory": None,
            "conflicts": [],
            "gap_resolved": False,
            "gaps_removed": 0,
        }

    if question:
        memory["title"] = question[:160]
        memory.setdefault("tags", [])
        if "gap_answer" not in memory["tags"]:
            memory["tags"] = list(memory["tags"]) + ["gap_answer"]

    dup = find_duplicate(tenant_id, memory)
    if dup and dup.get("confidence") == "confirmed":
        removed = 0
        if gap_memory_id or question:
            removed = resolve_knowledge_gap(
                tenant_id,
                memory_id=gap_memory_id,
                question=question,
            )
        return {
            "stored": False,
            "reason": "A similar memory already exists in Sibyl.",
            "memory": dup,
            "conflicts": [],
            "duplicate": True,
            "gap_resolved": removed > 0,
            "gaps_removed": removed,
        }

    conflicts = find_conflicts(tenant_id, memory)
    stored = store_memory(tenant_id, memory, skip_duplicate_check=True)

    for other in conflicts[:3]:
        store_memory(
            tenant_id,
            build_memory(
                memory_type="conflict",
                title=f"Potential conflict: {memory.get('title')}",
                content=(
                    f"New confirmed memory may conflict with existing memory "
                    f"'{other.get('title')}'. Do not assume which is correct."
                ),
                source=SOURCE_CONVERSATION,
                confidence="inferred",
                project_id=project_id,
                affected_components=memory.get("affected_components") or [],
                tags=["conflict"],
            ),
        )

    removed = 0
    if gap_memory_id or question:
        removed = resolve_knowledge_gap(
            tenant_id,
            memory_id=gap_memory_id,
            question=question,
        )

    return {
        "stored": True,
        "reason": None,
        "memory": stored,
        "conflicts": [
            {"memory_id": c.get("memory_id"), "title": c.get("title")} for c in conflicts
        ],
        "gap_resolved": removed > 0,
        "gaps_removed": removed,
    }


def candidate_confirmation_prompt(text: str) -> str | None:
    """If a chat message looks like institutional knowledge, ask before storing."""
    if not looks_like_institutional_statement(text):
        return None
    return (
        "This sounds like useful historical context. "
        "Should I record it as project memory in Sibyl? "
        "Reply yes to save it, or use Teach Kassandra to add more detail."
    )
