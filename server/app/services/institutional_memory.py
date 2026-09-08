"""Structured institutional memory persisted through Sibyl.

Kassandra reasons over observed / inferred / confirmed knowledge.
Sibyl is the sole persistence layer for this institutional memory.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from app.services.memory import get_memory_provider

logger = logging.getLogger(__name__)

Confidence = Literal["observed", "inferred", "confirmed"]
MemoryType = Literal[
    "observation",
    "architectural_decision",
    "historical_event",
    "inference",
    "knowledge_gap",
    "conflict",
    "drift",
    "constraint",
    "incident",
]

CATEGORY = "institutional"
GAPS_CATEGORY = "knowledge_gap"
BOOTSTRAP_REF = "bootstrap_summary"
INDEX_REF = "institutional_index"

VALID_CONFIDENCE = frozenset({"observed", "inferred", "confirmed"})
VALID_TYPES = frozenset(
    {
        "observation",
        "architectural_decision",
        "historical_event",
        "inference",
        "knowledge_gap",
        "conflict",
        "drift",
        "constraint",
        "incident",
    }
)

SOURCE_GITHUB = "github"
SOURCE_COMMIT = "commit"
SOURCE_PR = "pull_request"
SOURCE_ISSUE = "issue"
SOURCE_DOCS = "documentation"
SOURCE_ANALYSIS = "repository_analysis"
SOURCE_DEVELOPER = "developer"
SOURCE_CONVERSATION = "conversation"
SOURCE_INFERENCE = "system_inference"


def _slug(text: str, *, max_len: int = 48) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return (cleaned or "memory")[:max_len]


def _memory_key(memory_type: str, title: str, memory_id: str | None = None) -> str:
    mid = memory_id or uuid4().hex[:12]
    return f"{memory_type}__{_slug(title)}__{mid}"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _fingerprint(title: str, decision: str | None, content: str | None) -> str:
    raw = f"{title.strip().lower()}|{(decision or '').strip().lower()}|{(content or '')[:200].strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_memory(
    *,
    memory_type: MemoryType,
    title: str,
    content: str | None = None,
    decision: str | None = None,
    reason: str | None = None,
    alternatives: list[str] | None = None,
    outcome: str | None = None,
    source: str,
    source_reference: str | None = None,
    confidence: Confidence,
    project_id: str | None = None,
    historical_date: str | None = None,
    affected_components: list[str] | None = None,
    related_files: list[str] | None = None,
    related_commits: list[str] | None = None,
    related_prs: list[str] | None = None,
    tags: list[str] | None = None,
    priority: str | None = None,
    question: str | None = None,
    memory_id: str | None = None,
) -> dict[str, Any]:
    """Build a structured institutional memory object (section 10 of the bootstrap spec)."""
    if confidence not in VALID_CONFIDENCE:
        raise ValueError(f"Invalid confidence: {confidence}")
    if memory_type not in VALID_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type}")

    mid = memory_id or uuid4().hex
    now = _now_iso()
    return {
        "memory_id": mid,
        "project_id": project_id,
        "type": memory_type,
        "title": title.strip(),
        "content": (content or "").strip() or None,
        "decision": (decision or "").strip() or None,
        "reason": (reason or "").strip() or None,
        "alternatives": alternatives or [],
        "outcome": (outcome or "").strip() or None,
        "source": source,
        "source_reference": source_reference,
        "confidence": confidence,
        "created_at": now,
        "updated_at": now,
        "historical_date": historical_date,
        "affected_components": affected_components or [],
        "related_files": related_files or [],
        "related_commits": related_commits or [],
        "related_prs": related_prs or [],
        "tags": tags or [],
        "priority": priority,
        "question": (question or "").strip() or None,
        "fingerprint": _fingerprint(title, decision, content),
    }


def format_memory_line(memory: dict[str, Any]) -> str:
    """Plain-text line for LLM context with explicit provenance."""
    conf = str(memory.get("confidence") or "unknown").upper()
    mtype = str(memory.get("type") or "memory").replace("_", " ")
    title = memory.get("title") or "Untitled"
    parts = [f"[{conf}/{mtype}] {title}"]
    if memory.get("decision"):
        parts.append(f"Decision: {memory['decision']}")
    if memory.get("reason"):
        parts.append(f"Reason: {memory['reason']}")
    if memory.get("content") and memory.get("content") != memory.get("decision"):
        parts.append(str(memory["content"]))
    if memory.get("question"):
        parts.append(f"Gap: {memory['question']}")
    src = memory.get("source") or "unknown"
    parts.append(f"Source: {src}")
    if memory.get("source_reference"):
        parts.append(f"Ref: {memory['source_reference']}")
    return " | ".join(parts)


def _load_index(tenant_id: str) -> dict[str, Any]:
    import json

    memory = get_memory_provider(tenant_id)
    raw = memory.get_reference(INDEX_REF)
    if not raw:
        return {"keys": [], "fingerprints": {}}
    body = raw.get("body") if isinstance(raw, dict) else raw
    if isinstance(body, str):
        try:
            data = json.loads(body)
            return {
                "keys": list(data.get("keys") or []),
                "fingerprints": dict(data.get("fingerprints") or {}),
            }
        except json.JSONDecodeError:
            return {"keys": [], "fingerprints": {}}
    if isinstance(body, dict):
        return {
            "keys": list(body.get("keys") or []),
            "fingerprints": dict(body.get("fingerprints") or {}),
        }
    if isinstance(raw, dict) and ("keys" in raw or "fingerprints" in raw):
        return {
            "keys": list(raw.get("keys") or []),
            "fingerprints": dict(raw.get("fingerprints") or {}),
        }
    return {"keys": [], "fingerprints": {}}


def _save_index(tenant_id: str, index: dict[str, Any]) -> None:
    memory = get_memory_provider(tenant_id)
    import json

    memory.set_reference(
        INDEX_REF,
        json.dumps(index),
        metadata={"kind": "institutional_index", "updated_at": _now_iso()},
    )


def find_duplicate(tenant_id: str, candidate: dict[str, Any]) -> dict[str, Any] | None:
    """Return an existing memory with the same semantic fingerprint, if any."""
    fp = candidate.get("fingerprint") or _fingerprint(
        str(candidate.get("title") or ""),
        candidate.get("decision"),
        candidate.get("content"),
    )
    provider = get_memory_provider(tenant_id)
    index = _load_index(tenant_id)
    existing_key = (index.get("fingerprints") or {}).get(fp)
    if existing_key:
        for category in (CATEGORY, GAPS_CATEGORY):
            recalled = provider.recall(category, existing_key)
            if isinstance(recalled, dict):
                mem = _normalize_listed(recalled) or (
                    recalled if recalled.get("memory_id") else None
                )
                if mem:
                    return mem

    for item in list_memories(tenant_id):
        if item.get("fingerprint") == fp:
            return item
        if (
            candidate.get("type") == "knowledge_gap"
            and item.get("type") == "knowledge_gap"
            and (item.get("question") or item.get("title") or "").strip().lower()
            == (candidate.get("question") or candidate.get("title") or "").strip().lower()
        ):
            return item
    return None


def resolve_knowledge_gap(
    tenant_id: str,
    *,
    memory_id: str | None = None,
    question: str | None = None,
) -> int:
    """Remove matching knowledge-gap entries from Sibyl after the developer answers."""
    provider = get_memory_provider(tenant_id)
    removed = 0
    q_norm = (question or "").strip().lower()
    mid_norm = (memory_id or "").strip()

    # Prefer iterating Sibyl list so we have the real entity name/key
    try:
        raw_list = provider.list(GAPS_CATEGORY, limit=200) or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Sibyl list(knowledge_gap) failed for %s: %s", tenant_id, exc)
        raw_list = []

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("key")
        mem = _normalize_listed(item)
        if not mem and name:
            recalled = provider.recall(GAPS_CATEGORY, str(name))
            if isinstance(recalled, dict):
                mem = _normalize_listed(recalled) or (
                    recalled if recalled.get("memory_id") else None
                )
        if not mem or mem.get("type") != "knowledge_gap":
            continue
        mid = str(mem.get("memory_id") or "")
        mq = (mem.get("question") or mem.get("title") or "").strip().lower()
        match = False
        if mid_norm and mid == mid_norm:
            match = True
        if q_norm and mq == q_norm:
            match = True
        if not match:
            continue
        key = name or mem.get("sibyl_key")
        if not key:
            continue
        try:
            if provider.forget(GAPS_CATEGORY, str(key)):
                removed += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to forget gap %s: %s", key, exc)

    return removed


def dedupe_gaps_by_question(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for g in gaps:
        q = (g.get("question") or g.get("title") or "").strip().lower()
        if not q or q in seen:
            continue
        seen.add(q)
        unique.append(g)
    return unique


def find_conflicts(tenant_id: str, candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Heuristic conflict check: same affected component + opposing decisions."""
    components = {c.lower() for c in (candidate.get("affected_components") or []) if c}
    decision = (candidate.get("decision") or candidate.get("title") or "").lower()
    if not components or not decision:
        return []

    conflicts: list[dict[str, Any]] = []
    for item in list_memories(tenant_id, confidence=None):
        if item.get("type") == "knowledge_gap":
            continue
        if item.get("memory_id") == candidate.get("memory_id"):
            continue
        item_components = {c.lower() for c in (item.get("affected_components") or []) if c}
        if not components & item_components:
            continue
        other = (item.get("decision") or item.get("title") or "").lower()
        # Flag when both speak about the same component but titles/decisions differ substantially
        if other and other != decision and (
            ("must" in decision and "must" in other)
            or ("migrat" in decision and "migrat" in other)
            or ("use " in decision and "use " in other)
        ):
            if decision[:40] not in other and other[:40] not in decision:
                conflicts.append(item)
    return conflicts


def store_memory(
    tenant_id: str,
    memory: dict[str, Any],
    *,
    skip_duplicate_check: bool = False,
) -> dict[str, Any]:
    """Persist a structured memory into Sibyl WARM storage.

    Returns the stored memory, or the existing duplicate when skipped.
    """
    if not skip_duplicate_check:
        dup = find_duplicate(tenant_id, memory)
        if dup:
            logger.info(
                "Skipping duplicate institutional memory for %s: %s",
                tenant_id,
                memory.get("title"),
            )
            return {**dup, "_duplicate": True}

    key = _memory_key(
        str(memory.get("type") or "observation"),
        str(memory.get("title") or "memory"),
        str(memory.get("memory_id") or "")[:12] or None,
    )
    memory = {**memory, "sibyl_key": key, "updated_at": _now_iso()}
    provider = get_memory_provider(tenant_id)
    category = GAPS_CATEGORY if memory.get("type") == "knowledge_gap" else CATEGORY
    provider.remember(category, key, memory)

    index = _load_index(tenant_id)
    keys = list(index.get("keys") or [])
    if key not in keys:
        keys.append(key)
    fingerprints = dict(index.get("fingerprints") or {})
    fingerprints[memory["fingerprint"]] = key
    _save_index(tenant_id, {"keys": keys[-500:], "fingerprints": fingerprints})

    # Searchable journal line for FTS
    provider.save_context(
        inputs={
            "event": "institutional_memory",
            "type": memory.get("type"),
            "confidence": memory.get("confidence"),
            "title": memory.get("title"),
        },
        outputs={"summary": format_memory_line(memory)},
    )
    return memory


def store_many(tenant_id: str, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    for mem in memories:
        stored.append(store_memory(tenant_id, mem))
    return stored


def _normalize_listed(item: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize Sibyl list/recall shapes into our memory dict."""
    if item.get("memory_id") and item.get("type"):
        return item
    body = item.get("body")
    if isinstance(body, dict) and body.get("memory_id"):
        return body
    # list() may return {category, name, body, ...}
    if isinstance(body, dict) and body.get("title"):
        return body
    return None


def list_memories(
    tenant_id: str,
    *,
    confidence: Confidence | None = None,
    memory_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List institutional memories from Sibyl."""
    provider = get_memory_provider(tenant_id)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    for category in (CATEGORY, GAPS_CATEGORY):
        try:
            raw_list = provider.list(category, limit=limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sibyl list(%s) failed for %s: %s", category, tenant_id, exc)
            continue
        for item in raw_list or []:
            if not isinstance(item, dict):
                continue
            mem = _normalize_listed(item)
            if not mem:
                # Try recall by name
                name = item.get("name") or item.get("key")
                if name:
                    recalled = provider.recall(category, str(name))
                    if isinstance(recalled, dict):
                        mem = _normalize_listed(recalled) or (
                            recalled if recalled.get("memory_id") else None
                        )
            if not mem:
                continue
            mid = str(mem.get("memory_id") or mem.get("sibyl_key") or "")
            if mid in seen:
                continue
            if confidence and mem.get("confidence") != confidence:
                continue
            if memory_type and mem.get("type") != memory_type:
                continue
            seen.add(mid)
            results.append(mem)

    return results


def count_by_confidence(tenant_id: str) -> dict[str, int]:
    counts = {"observed": 0, "inferred": 0, "confirmed": 0, "gaps": 0}
    for mem in list_memories(tenant_id):
        if mem.get("type") == "knowledge_gap":
            counts["gaps"] += 1
            continue
        conf = mem.get("confidence")
        if conf in counts:
            counts[conf] += 1
    return counts


def list_knowledge_gaps(
    tenant_id: str,
    *,
    priority: str | None = None,
) -> list[dict[str, Any]]:
    gaps = [
        m
        for m in list_memories(tenant_id, memory_type="knowledge_gap")
        if m.get("type") == "knowledge_gap"
    ]
    if priority:
        gaps = [g for g in gaps if (g.get("priority") or "").lower() == priority.lower()]

    order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: order.get(str(g.get("priority") or "medium").lower(), 9))
    return gaps


def save_bootstrap_summary(tenant_id: str, summary: dict[str, Any]) -> None:
    import json

    provider = get_memory_provider(tenant_id)
    summary = {**summary, "updated_at": _now_iso()}
    provider.set_reference(
        BOOTSTRAP_REF,
        json.dumps(summary),
        metadata={"kind": "bootstrap_summary", "updated_at": summary["updated_at"]},
    )
    provider.remember("bootstrap", "summary", summary)


def get_bootstrap_summary(tenant_id: str) -> dict[str, Any] | None:
    import json

    provider = get_memory_provider(tenant_id)
    recalled = provider.recall("bootstrap", "summary")
    if isinstance(recalled, dict):
        if recalled.get("architecture") or recalled.get("stack"):
            return recalled
        body = recalled.get("body")
        if isinstance(body, dict) and (body.get("architecture") or body.get("stack")):
            return body

    raw = provider.get_reference(BOOTSTRAP_REF)
    if not raw:
        return None
    body = raw.get("body") if isinstance(raw, dict) else raw
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    if isinstance(body, dict):
        return body
    if isinstance(raw, dict) and ("architecture" in raw or "stack" in raw):
        return raw
    return None


def build_understanding_report(tenant_id: str, repo_full_name: str) -> dict[str, Any]:
    """Assemble the bootstrap summary UI payload (section 17)."""
    cached = get_bootstrap_summary(tenant_id)
    memories = list_memories(tenant_id)
    gaps = dedupe_gaps_by_question(
        [m for m in memories if m.get("type") == "knowledge_gap"]
    )
    observations = [m for m in memories if m.get("confidence") == "observed" and m.get("type") != "knowledge_gap"]
    inferred = [m for m in memories if m.get("confidence") == "inferred"]
    confirmed = [m for m in memories if m.get("confidence") == "confirmed"]

    # Dedupe architecture rows by title (re-analyze can leave near-duplicates)
    architecture_items: list[dict[str, Any]] = []
    seen_arch: set[str] = set()
    for m in memories:
        if m.get("type") != "observation" or "architecture" not in (m.get("tags") or []):
            continue
        title = (m.get("title") or "").strip().lower()
        if title in seen_arch:
            continue
        seen_arch.add(title)
        architecture_items.append(m)

    evolution_items = [
        m
        for m in memories
        if m.get("type") in {"historical_event", "architectural_decision", "inference"}
        and m.get("type") != "knowledge_gap"
    ]

    high_gaps = [g for g in gaps if (g.get("priority") or "").lower() == "high"]

    report = {
        "repo_full_name": repo_full_name,
        "headline": (
            "I don't need you to explain the repository. "
            "I only need the context that the repository cannot tell me."
        ),
        "architecture": [
            {
                "title": m.get("title"),
                "content": m.get("content") or m.get("decision"),
                "confidence": m.get("confidence"),
            }
            for m in architecture_items[:20]
        ],
        "historical_evolution": [
            {
                "title": m.get("title"),
                "decision": m.get("decision"),
                "reason": m.get("reason"),
                "confidence": m.get("confidence"),
                "source": m.get("source"),
            }
            for m in evolution_items[:20]
        ],
        "counts": {
            "observed": len(observations),
            "inferred": len(inferred),
            "confirmed": len(confirmed),
            "knowledge_gaps": len(gaps),
            "high_priority_gaps": len(high_gaps),
        },
        "knowledge_gaps": [
            {
                "memory_id": g.get("memory_id"),
                "question": g.get("question") or g.get("title"),
                "priority": g.get("priority") or "medium",
                "affected_components": g.get("affected_components") or [],
                "reason": g.get("reason") or g.get("content"),
            }
            for g in sorted(
                gaps,
                key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(
                    str(x.get("priority") or "medium").lower(), 9
                ),
            )[:12]
        ],
        "confidence_areas": (cached or {}).get("confidence_areas")
        or {
            "architecture": "high" if len(architecture_items) >= 3 else "medium",
            "historical_evolution": "medium" if evolution_items else "low",
            "institutional_why": "high"
            if confirmed
            else ("unknown" if high_gaps else "low"),
        },
        "interview_intro": (
            f"I've analyzed your repository.\n\n"
            f"I understand most of the current architecture and a portion of its evolution.\n\n"
            f"I found {len(high_gaps) or len(gaps)} area(s) where the repository cannot "
            f"reliably tell me WHY certain decisions were made."
            if gaps
            else "I've analyzed your repository. No high-value knowledge gaps were flagged yet."
        ),
        "updated_at": (cached or {}).get("updated_at") or _now_iso(),
    }
    return report


def developer_source_label(full_name: str | None) -> str:
    name = (full_name or "").strip() or "account owner"
    return f"developer-{name}"
