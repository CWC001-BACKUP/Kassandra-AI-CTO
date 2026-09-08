"""Cross-repository comparison — resolve scope, gather evidence, and answer."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from app.models import Project
from app.services.evidence import (
    evidence_ref,
    merge_evidence,
    normalize_evidence,
    repo_stats_evidence_refs,
    sibyl_memory_evidence,
)
from app.services.evidence_integrity import (
    EvidenceLevel,
    collect_known_shas,
    infer_evidence_level,
    sanitize_llm_reply,
)
from app.services.github import get_repo_languages, list_commits
from app.services.llm import LLMError, chat_completion, is_llm_configured
from app.services.repo_context import format_repo_stats_block, gather_repo_stats

if TYPE_CHECKING:
    from app.models import User

logger = logging.getLogger(__name__)

MAX_CROSS_REPO = 5

CROSS_REPO_PATTERN = re.compile(
    r"\b("
    r"compare|comparison|contrast|versus|vs\.?|"
    r"both repos?(?:itories)?|all (?:my )?repos?(?:itories)?|each repo|"
    r"across repos?|between repos?|multi-?repo|two repos?|"
    r"both projects?|all projects?|"
    r"unified report|combined report|cross-?repo|"
    r"analyze both|report on both|compare both"
    r")\b",
    re.I,
)

CROSS_REPO_SYSTEM_ADDENDUM = """
Cross-repository mode — multiple repositories are in scope for this answer.

Rules:
- Use ONLY the per-repository evidence blocks below; do not invent data for any repo
- Label every fact with its repository (owner/name)
- Do not merge contributors, commits, or stats across repos without an explicit comparison
- Sibyl memory sections are per-repo; never conflate institutional memory between repos
- For comparisons, use a clear structured format (side-by-side or per-repo sections)
- If evidence for a repo is missing, say so — do not guess
"""


def is_cross_repo_question(message: str) -> bool:
    return bool(CROSS_REPO_PATTERN.search(message))


def match_projects_in_message(message: str, projects: list[Project]) -> list[Project]:
    text = message.lower()
    seen: set[str] = set()
    matched: list[Project] = []

    for project in projects:
        full = project.repo_full_name.lower()
        short = full.rsplit("/", 1)[-1]
        owner = full.rsplit("/", 1)[0] if "/" in full else ""
        hits = (
            full in text
            or (len(short) >= 3 and re.search(rf"\b{re.escape(short)}\b", text) is not None)
            or (
                owner
                and short
                and re.search(rf"\b{re.escape(owner)}/{re.escape(short)}\b", text) is not None
            )
        )
        if hits and project.id not in seen:
            seen.add(project.id)
            matched.append(project)

    return matched


def is_single_repo_commit_scope(message: str) -> bool:
    """True when the question targets commits in one repo, not a cross-repo comparison."""
    from app.services.repo_context import (
        is_commit_compare_question,
        is_multi_commit_compare_question,
        mentions_commit_sha,
        parse_recent_commit_count,
    )

    if is_multi_commit_compare_question(message):
        return True
    if mentions_commit_sha(message) and is_commit_compare_question(message):
        return True
    if parse_recent_commit_count(message) and re.search(
        r"\b(evolved|evolution|progression|changed over)\b",
        message,
        re.I,
    ):
        return True
    return False


def resolve_cross_repo_projects(
    message: str,
    primary: Project | None,
    all_projects: list[Project],
    explicit_ids: list[str] | None = None,
) -> list[Project]:
    """Return 2+ projects when a cross-repo question is in scope."""
    if is_single_repo_commit_scope(message):
        return []

    by_id = {p.id: p for p in all_projects}

    if explicit_ids:
        resolved = [by_id[pid] for pid in explicit_ids if pid in by_id]
        if len(resolved) >= 2:
            return resolved[:MAX_CROSS_REPO]

    if not is_cross_repo_question(message) and not explicit_ids:
        return []

    named = match_projects_in_message(message, all_projects)
    if len(named) >= 2:
        return named[:MAX_CROSS_REPO]

    if primary and len(named) == 1 and named[0].id != primary.id:
        return [primary, named[0]][:MAX_CROSS_REPO]

    if len(all_projects) >= 2:
        if primary:
            ordered = [primary] + [p for p in all_projects if p.id != primary.id]
            return ordered[:MAX_CROSS_REPO]
        return all_projects[:MAX_CROSS_REPO]

    return []


async def gather_cross_repo_snapshot(access_token: str, project: Project) -> dict:
    """Lightweight per-repo snapshot for comparison (stats + recent commits + languages)."""
    branch = project.default_branch or "main"
    full_name = project.repo_full_name

    stats_result, commits_result, languages_result = await asyncio.gather(
        gather_repo_stats(access_token, project),
        list_commits(access_token, full_name, branch=branch, per_page=8),
        get_repo_languages(access_token, full_name),
        return_exceptions=True,
    )

    stats = stats_result if isinstance(stats_result, dict) else {}
    commits = commits_result if isinstance(commits_result, list) else []
    languages = languages_result if isinstance(languages_result, dict) else {}

    return {
        "project_id": project.id,
        "repo": full_name,
        "branch": branch,
        "stats": stats,
        "recent_commits": commits,
        "languages": languages,
    }


async def gather_cross_repo_snapshots(
    access_token: str,
    projects: list[Project],
) -> list[dict]:
    results = await asyncio.gather(
        *[gather_cross_repo_snapshot(access_token, p) for p in projects],
        return_exceptions=True,
    )
    snapshots: list[dict] = []
    for project, result in zip(projects, results, strict=True):
        if isinstance(result, Exception):
            logger.warning("Cross-repo snapshot failed for %s: %s", project.repo_full_name, result)
            snapshots.append(
                {
                    "project_id": project.id,
                    "repo": project.repo_full_name,
                    "branch": project.default_branch or "main",
                    "stats": {},
                    "recent_commits": [],
                    "languages": {},
                    "error": str(result),
                }
            )
        else:
            snapshots.append(result)
    return snapshots


def format_snapshot_block(snapshot: dict) -> str:
    repo = snapshot.get("repo", "unknown")
    lines = [f"=== {repo} ==="]

    if snapshot.get("error"):
        lines.append(f"Evidence fetch failed: {snapshot['error']}")
        return "\n".join(lines)

    stats = snapshot.get("stats") or {}
    if stats:
        lines.append(format_repo_stats_block(stats))

    languages = snapshot.get("languages") or {}
    if languages:
        lang_list = ", ".join(f"{k} ({v})" for k, v in list(languages.items())[:8])
        lines.append(f"Languages (bytes): {lang_list}")

    commits = snapshot.get("recent_commits") or []
    if commits:
        lines.append(f"\nRecent commits on {snapshot.get('branch', 'main')}:")
        for commit in commits[:8]:
            sha = (commit.get("sha") or "")[:7]
            title = commit.get("title") or commit.get("message", "").split("\n")[0]
            author = commit.get("author") or "unknown"
            date = commit.get("date") or ""
            lines.append(f"• {sha} {title} — {author} ({date})")

    return "\n".join(lines)


def format_cross_repo_context_for_llm(snapshots: list[dict]) -> str:
    blocks = [format_snapshot_block(s) for s in snapshots]
    return "\n\n".join(blocks)


def cross_repo_evidence_refs(snapshots: list[dict]) -> list[dict]:
    refs: list[dict] = []
    for snapshot in snapshots:
        repo = snapshot.get("repo", "repository")
        stats = snapshot.get("stats") or {}
        if stats:
            refs.extend(repo_stats_evidence_refs(stats)[:2])
        else:
            refs.append(
                evidence_ref(
                    f"{repo} (cross-repo scope)",
                    url=f"https://github.com/{repo}",
                    kind="cross_repo",
                )
            )
    return refs


def _search_memory(tenant_id: str, query: str) -> list:
    from app.services.memory import get_memory_provider

    try:
        provider = get_memory_provider(tenant_id)
        results = provider.search(query)
        return list(results) if results else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Memory search failed for %s: %s", tenant_id, exc)
        return []


def _format_memory_block(repo: str, hits: list, *, sibyl_enabled: bool) -> str:
    if not sibyl_enabled:
        return f"Sibyl memory for {repo}: OFF"
    if not hits:
        return f"Sibyl memory for {repo}: no relevant entries"
    lines = [f"Sibyl memory for {repo}:"]
    for hit in hits[:6]:
        content = hit.get("content") or hit.get("text") or str(hit) if isinstance(hit, dict) else str(hit)
        lines.append(f"• {content}")
    return "\n".join(lines)


def _answer_cross_repo_without_llm(snapshots: list[dict], memory_blocks: list[str]) -> str:
    repo_names = ", ".join(s["repo"] for s in snapshots)
    parts = [
        f"Cross-repository comparison for: {repo_names}",
        "",
        format_cross_repo_context_for_llm(snapshots),
    ]
    if any("Sibyl memory" in block and "no relevant" not in block for block in memory_blocks):
        parts.append("\n--- Sibyl institutional memory ---")
        parts.extend(memory_blocks)
    parts.append(
        "\nConfigure LLM in server/.env for AI-generated cross-repo analysis and reports."
    )
    return "\n".join(parts)


async def process_cross_repo_message(
    user: User,
    message: str,
    projects: list[Project],
    *,
    history: list[dict[str, str]] | None = None,
    sibyl_enabled: bool = True,
) -> dict:
    """Answer a question spanning multiple repositories with combined GitHub evidence."""
    from app.services.chat import SYSTEM_PROMPT, _clean_response, _result

    text = message.strip()
    history = history or []
    primary = projects[0]

    if not user.github_access_token:
        return _result(
            "Connect GitHub to compare repositories.",
            "system",
            primary,
            [],
            [],
        )

    snapshots = await gather_cross_repo_snapshots(user.github_access_token, projects)
    evidence_block = format_cross_repo_context_for_llm(snapshots)
    evidence_refs = cross_repo_evidence_refs(snapshots)

    memory_hits: list = []
    memory_blocks: list[str] = []
    if sibyl_enabled:
        for project in projects:
            hits = _search_memory(project.repo_full_name, text)
            memory_hits.extend(hits)
            memory_blocks.append(
                _format_memory_block(project.repo_full_name, hits, sibyl_enabled=sibyl_enabled)
            )
    else:
        memory_blocks = [
            _format_memory_block(p.repo_full_name, [], sibyl_enabled=False) for p in projects
        ]

    repo_label = " + ".join(p.repo_full_name for p in projects)

    if not is_llm_configured():
        reply = _clean_response(_answer_cross_repo_without_llm(snapshots, memory_blocks))
        return _result(
            reply,
            "cross_repo",
            primary,
            memory_hits,
            evidence_refs,
            sibyl_enabled=sibyl_enabled,
            has_repo_history=True,
            evidence_level=EvidenceLevel.REPOSITORY_HISTORY,
        )

    context_parts = [
        CROSS_REPO_SYSTEM_ADDENDUM,
        "Per-repository Sibyl memory:\n" + "\n\n".join(memory_blocks),
        f"Per-repository GitHub evidence (pre-fetched — use only this):\n{evidence_block}",
    ]

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(repo_name=repo_label)
            + "\n\n"
            + "\n\n".join(context_parts),
        },
    ]
    for msg in history[-8:]:
        if msg["role"] in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": text})

    try:
        raw = await chat_completion(messages)
        known_shas = collect_known_shas(*[s.get("recent_commits") for s in snapshots])
        reply = sanitize_llm_reply(
            _clean_response(raw),
            known_shas=known_shas,
            history=history,
        )
    except LLMError as exc:
        reply = _clean_response(
            f"Cross-repo analysis failed ({exc}).\n\n{evidence_block[:4000]}"
        )

    github_evidence = normalize_evidence(evidence_refs)
    if sibyl_enabled and memory_hits:
        final_evidence = merge_evidence(github_evidence, sibyl_memory_evidence(memory_hits))
    else:
        final_evidence = github_evidence

    level = infer_evidence_level(
        "cross_repo",
        has_repo_history=True,
        has_commit_detail=False,
        is_session=False,
    )

    return {
        "reply": reply,
        "source": "cross_repo",
        "intent": "cross_repo_compare",
        "project_id": primary.id,
        "memory_hits": len(memory_hits),
        "evidence": final_evidence,
        "last_commit_sha": None,
        "previous_commit_sha": None,
        "evidence_level": int(level),
        "evidence_level_name": level.name,
    }
