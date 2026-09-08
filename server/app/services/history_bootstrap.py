"""Bootstrap knowledge-gap detection and history/PR enrichment for institutional memory."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.architecture_extract import (
    architecture_memories_from_stack,
    classify_commit_signal,
    documentation_memory,
    extract_stack_from_manifests,
    history_memory_from_commit,
    inference_from_history,
    is_meaningful_commit_message,
)
from app.services.github import (
    GitHubError,
    list_commits,
    list_issues,
    list_pull_requests,
)
from app.services.institutional_memory import (
    SOURCE_ANALYSIS,
    SOURCE_ISSUE,
    SOURCE_PR,
    build_memory,
    build_understanding_report,
    save_bootstrap_summary,
    store_many,
    store_memory,
)

logger = logging.getLogger(__name__)


def _gap(
    question: str,
    *,
    priority: str,
    components: list[str],
    reason: str,
    project_id: str | None,
    related_commits: list[str] | None = None,
) -> dict[str, Any]:
    return build_memory(
        memory_type="knowledge_gap",
        title=question,
        question=question,
        content=reason,
        reason=reason,
        source=SOURCE_ANALYSIS,
        confidence="observed",  # the gap itself is an observed unknown
        project_id=project_id,
        affected_components=components,
        related_commits=related_commits or [],
        priority=priority,
        tags=["knowledge_gap", priority],
    )


def detect_knowledge_gaps(
    *,
    stack: dict[str, list[str]],
    history_memories: list[dict[str, Any]],
    inferred_memories: list[dict[str, Any]],
    project_id: str | None,
) -> list[dict[str, Any]]:
    """Only ask questions that materially improve architectural reasoning."""
    gaps: list[dict[str, Any]] = []
    titles = " ".join(
        (m.get("title") or "") + " " + (m.get("decision") or "")
        for m in history_memories + inferred_memories
    ).lower()

    db_techs = stack.get("database") or []
    if db_techs:
        gaps.append(
            _gap(
                f"Why was {db_techs[0]} selected as the database?",
                priority="high",
                components=["database"],
                reason=(
                    "Database technology is observed in the repository, but the decision "
                    "rationale is not recoverable from code alone."
                ),
                project_id=project_id,
            )
        )

    if "migrat" in titles or "mongo" in titles or any(
        "migration" in (m.get("tags") or []) for m in history_memories + inferred_memories
    ):
        gaps.append(
            _gap(
                "Why was the database (or another core store) migrated?",
                priority="high",
                components=["database"],
                reason="History suggests a migration, but the failure mode or constraint is unknown.",
                project_id=project_id,
                related_commits=[
                    c
                    for m in history_memories
                    for c in (m.get("related_commits") or [])
                ][:5],
            )
        )

    if stack.get("authentication") or "auth" in titles:
        gaps.append(
            _gap(
                "Why was authentication designed or redesigned this way?",
                priority="high",
                components=["authentication"],
                reason=(
                    "Authentication approach is visible, but whether it is intentional, "
                    "temporary, or driven by past incidents is unknown."
                ),
                project_id=project_id,
            )
        )

    if stack.get("api"):
        gaps.append(
            _gap(
                "Is the current API architecture intentional or transitional?",
                priority="medium",
                components=["api"],
                reason="API style can be observed; strategic intent usually cannot.",
                project_id=project_id,
            )
        )

    gaps.append(
        _gap(
            "Were previous production incidents responsible for any current constraints?",
            priority="high",
            components=["reliability"],
            reason="Incidents and lessons learned are rarely fully captured in git history.",
            project_id=project_id,
        )
    )

    gaps.append(
        _gap(
            "Are there business or customer constraints that explain unusual technical decisions?",
            priority="medium",
            components=["product"],
            reason="Business constraints are institutional knowledge, not repository facts.",
            project_id=project_id,
        )
    )

    # Deduplicate by question text
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for g in gaps:
        q = (g.get("question") or g.get("title") or "").lower()
        if q in seen:
            continue
        seen.add(q)
        unique.append(g)
    return unique


async def collect_history_signals(
    token: str,
    repo_name: str,
    *,
    branch: str,
    project_id: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Fetch commits/PRs/issues and build observed + inferred memories.

    Degrades gracefully when GitHub history is unavailable.
    """
    meta = {
        "commits_scanned": 0,
        "meaningful_commits": 0,
        "prs_scanned": 0,
        "issues_scanned": 0,
        "history_available": True,
        "prs_available": True,
        "issues_available": True,
    }
    history: list[dict[str, Any]] = []
    inferred: list[dict[str, Any]] = []

    commits: list[dict] = []
    try:
        commits = await list_commits(token, repo_name, branch=branch, per_page=40)
        meta["commits_scanned"] = len(commits)
    except GitHubError as exc:
        logger.warning("Commit history unavailable for %s: %s", repo_name, exc)
        meta["history_available"] = False

    for commit in commits:
        title = commit.get("title") or ""
        if not is_meaningful_commit_message(title):
            continue
        signal = classify_commit_signal(title) or "significant_change"
        history.append(
            history_memory_from_commit(commit, project_id=project_id, signal=signal)
        )
    meta["meaningful_commits"] = len(history)
    inferred.extend(inference_from_history(commits, project_id=project_id))

    try:
        prs = await list_pull_requests(token, repo_name, state="all", per_page=15)
        meta["prs_scanned"] = len(prs)
        for pr in prs:
            title = pr.get("title") or ""
            lower = title.lower()
            if not any(
                k in lower
                for k in (
                    "migrat",
                    "refactor",
                    "auth",
                    "security",
                    "breaking",
                    "replace",
                    "architect",
                    "database",
                    "performance",
                )
            ):
                continue
            history.append(
                build_memory(
                    memory_type="historical_event",
                    title=f"PR #{pr.get('number')}: {title[:100]}",
                    content=(
                        "Pull request title suggests an architectural or migration-related change. "
                        "PR discussions often contain the WHY; title alone is observed evidence."
                    ),
                    decision=title[:200],
                    source=SOURCE_PR,
                    source_reference=str(pr.get("html_url") or pr.get("number")),
                    confidence="observed",
                    project_id=project_id,
                    related_prs=[str(pr.get("number"))] if pr.get("number") else [],
                    tags=["pull_request", "git_history"],
                )
            )
            # Prefer richer WHY when title itself encodes a reason
            if re.search(r"\b(because|to fix|to avoid|due to)\b", lower):
                inferred.append(
                    build_memory(
                        memory_type="inference",
                        title=f"Possible rationale from PR #{pr.get('number')}",
                        content=f"PR title may encode rationale: {title}",
                        source=SOURCE_PR,
                        source_reference=str(pr.get("html_url") or pr.get("number")),
                        confidence="inferred",
                        project_id=project_id,
                        related_prs=[str(pr.get("number"))] if pr.get("number") else [],
                        tags=["pull_request"],
                    )
                )
    except GitHubError as exc:
        logger.warning("PR history unavailable for %s: %s", repo_name, exc)
        meta["prs_available"] = False

    try:
        issues = await list_issues(token, repo_name, state="all", per_page=15)
        meta["issues_scanned"] = len(issues)
        for issue in issues:
            title = issue.get("title") or ""
            lower = title.lower()
            if not any(k in lower for k in ("outage", "incident", "postmortem", "root cause", "rfc")):
                continue
            history.append(
                build_memory(
                    memory_type="incident",
                    title=f"Issue #{issue.get('number')}: {title[:100]}",
                    content="Issue title suggests an incident or RFC worth preserving.",
                    source=SOURCE_ISSUE,
                    source_reference=str(issue.get("number")),
                    confidence="observed",
                    project_id=project_id,
                    tags=["issue", "incident"],
                )
            )
    except GitHubError as exc:
        logger.warning("Issue history unavailable for %s: %s", repo_name, exc)
        meta["issues_available"] = False

    return history, inferred, meta


def run_bootstrap_ingestion(
    *,
    tenant_id: str,
    project_id: str | None,
    repo_full_name: str,
    languages: dict[str, int],
    root_files: list[str],
    config_snippets: dict[str, str],
    readme: str | None,
    history_memories: list[dict[str, Any]],
    inferred_memories: list[dict[str, Any]],
    history_meta: dict[str, Any],
) -> dict[str, Any]:
    """Classify knowledge, store into Sibyl, detect gaps, write bootstrap summary."""
    stack = extract_stack_from_manifests(
        config_snippets,
        root_files=root_files,
        languages=languages,
        readme=readme,
    )
    arch_memories = architecture_memories_from_stack(
        stack,
        project_id=project_id,
        repo_full_name=repo_full_name,
    )
    doc_mem = documentation_memory(readme, project_id=project_id, repo=repo_full_name)

    to_store = list(arch_memories)
    if doc_mem:
        to_store.append(doc_mem)
    to_store.extend(history_memories)
    to_store.extend(inferred_memories)

    gaps = detect_knowledge_gaps(
        stack=stack,
        history_memories=history_memories,
        inferred_memories=inferred_memories,
        project_id=project_id,
    )
    to_store.extend(gaps)

    stored = store_many(tenant_id, to_store)

    # Confidence areas for the understanding UI
    confidence_areas = {
        "architecture": "high" if len(arch_memories) >= 3 else ("medium" if arch_memories else "low"),
        "historical_evolution": (
            "medium"
            if history_meta.get("history_available") and history_memories
            else ("unavailable" if not history_meta.get("history_available") else "low")
        ),
        "database_decision_reason": "unknown" if stack.get("database") else "n/a",
        "api_architecture_rationale": "unknown" if stack.get("api") else "n/a",
        "authentication_flow": "medium" if stack.get("authentication") else "unknown",
        "institutional_why": "unknown",
    }

    summary = {
        "repo_full_name": repo_full_name,
        "stack": stack,
        "architecture": [
            {"title": m["title"], "content": m.get("content"), "confidence": "observed"}
            for m in arch_memories
        ],
        "historical_evolution": [
            {
                "title": m.get("title"),
                "decision": m.get("decision"),
                "confidence": m.get("confidence"),
                "source": m.get("source"),
            }
            for m in history_memories + inferred_memories
        ],
        "knowledge_gaps": [
            {
                "memory_id": g.get("memory_id"),
                "question": g.get("question"),
                "priority": g.get("priority"),
                "affected_components": g.get("affected_components"),
            }
            for g in gaps
        ],
        "counts": {
            "observed": sum(1 for m in stored if m.get("confidence") == "observed" and m.get("type") != "knowledge_gap"),
            "inferred": sum(1 for m in stored if m.get("confidence") == "inferred"),
            "confirmed": sum(1 for m in stored if m.get("confidence") == "confirmed"),
            "knowledge_gaps": len(gaps),
            "stored": len([m for m in stored if not m.get("_duplicate")]),
        },
        "confidence_areas": confidence_areas,
        "history_meta": history_meta,
    }
    save_bootstrap_summary(tenant_id, summary)

    # Also store a compact architecture overview entity for recall
    store_memory(
        tenant_id,
        build_memory(
            memory_type="observation",
            title="Architecture overview",
            content="; ".join(
                f"{layer}: {', '.join(items)}" for layer, items in stack.items()
            )
            or "Stack not yet determined from manifests.",
            source=SOURCE_ANALYSIS,
            source_reference=repo_full_name,
            confidence="observed",
            project_id=project_id,
            tags=["architecture", "overview"],
            affected_components=list(stack.keys()),
        ),
    )

    return build_understanding_report(tenant_id, repo_full_name)
