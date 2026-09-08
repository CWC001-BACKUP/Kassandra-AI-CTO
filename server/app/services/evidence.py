"""Structured, traceable evidence refs for chat answers.

GitHub repository evidence and Sibyl institutional memory are kept separate —
per the Sibyl hackathon requirement that memory is a distinct, load-bearing layer:
https://hack.sibyllabs.org/
"""

from __future__ import annotations

from typing import Any, Literal

EvidenceSource = Literal["github", "sibyl", "session"]

SIBYL_DOCS_URL = "https://docs.sibyllabs.org/memory/"


def evidence_ref(
    label: str,
    *,
    url: str | None = None,
    source: EvidenceSource = "github",
    kind: str | None = None,
) -> dict[str, str | None]:
    return {"label": label, "url": url, "source": source, "kind": kind}


def github_repo_url(repo_full_name: str) -> str:
    return f"https://github.com/{repo_full_name}"


def github_commit_url(repo_full_name: str, sha: str) -> str:
    return f"https://github.com/{repo_full_name}/commit/{sha}"


def github_file_url(repo_full_name: str, sha: str, path: str) -> str:
    return f"https://github.com/{repo_full_name}/blob/{sha}/{path}"


def github_actions_url(repo_full_name: str) -> str:
    return f"https://github.com/{repo_full_name}/actions"


def normalize_evidence(items: list[Any] | None) -> list[dict[str, str | None]]:
    """Coerce legacy string evidence or dict refs into a uniform list."""
    if not items:
        return []
    out: list[dict[str, str | None]] = []
    for item in items:
        if isinstance(item, str):
            out.append(evidence_ref(item))
        elif isinstance(item, dict) and item.get("label"):
            out.append(
                evidence_ref(
                    str(item["label"]),
                    url=item.get("url"),
                    source=item.get("source") or "github",  # type: ignore[arg-type]
                    kind=item.get("kind"),
                )
            )
    return out


def merge_evidence(*parts: list[Any]) -> list[dict[str, str | None]]:
    seen: set[tuple[str, str | None, str]] = set()
    merged: list[dict[str, str | None]] = []
    for part in parts:
        for ref in normalize_evidence(part):
            key = (ref["label"] or "", ref.get("url"), ref.get("source") or "github")
            if key in seen:
                continue
            seen.add(key)
            merged.append(ref)
    return merged


def sibyl_memory_evidence(hits: list[Any], *, max_items: int = 5) -> list[dict[str, str | None]]:
    """Sibyl Memory hits — always labeled source=sibyl, never mixed with GitHub."""
    refs: list[dict[str, str | None]] = []
    for hit in hits[:max_items]:
        if isinstance(hit, dict):
            content = hit.get("content") or hit.get("text") or ""
        else:
            content = str(hit)
        content = str(content).strip()
        if not content:
            continue
        snippet = content if len(content) <= 72 else content[:69] + "..."
        refs.append(
            evidence_ref(
                snippet,
                url=SIBYL_DOCS_URL,
                source="sibyl",
                kind="memory",
            )
        )
    return refs


def session_evidence(label: str) -> dict[str, str | None]:
    return evidence_ref(label, source="session", kind="chat")


def commit_manifest_evidence_refs(
    detail: dict, repo_full_name: str, *, max_files: int = 12
) -> list[dict[str, str | None]]:
    """First-class file manifest evidence (review §9)."""
    sha = detail.get("sha") or ""
    short = detail.get("short_sha") or sha[:7]
    files = detail.get("files") or []
    if not files:
        return []

    refs: list[dict[str, str | None]] = [
        evidence_ref(
            f"File manifest — commit {short} ({len(files)} files)",
            url=github_commit_url(repo_full_name, sha) if sha else None,
            kind="manifest",
        )
    ]
    for f in files[:max_files]:
        path = f.get("filename", "")
        if not path:
            continue
        status = f.get("status", "modified")
        adds = f.get("additions", 0)
        dels = f.get("deletions", 0)
        refs.append(
            evidence_ref(
                f"{path} ({status}, +{adds}/-{dels})",
                url=github_file_url(repo_full_name, sha, path) if sha else None,
                kind="manifest_file",
            )
        )
    if len(files) > max_files:
        refs.append(
            evidence_ref(f"… and {len(files) - max_files} more files", kind="manifest")
        )
    return refs


def commit_evidence_refs(detail: dict, repo_full_name: str) -> list[dict[str, str | None]]:
    sha = detail.get("sha") or ""
    short = detail.get("short_sha") or sha[:7]
    refs: list[dict[str, str | None]] = [
        evidence_ref(
            f"Commit {short}",
            url=github_commit_url(repo_full_name, sha) if sha else None,
            kind="commit",
        )
    ]
    file_count = detail.get("file_count")
    if file_count is None:
        file_count = len(detail.get("files") or [])
    if file_count:
        refs.append(
            evidence_ref(f"{file_count} files changed", kind="commit_stats")
        )
    refs.extend(commit_manifest_evidence_refs(detail, repo_full_name))
    if detail.get("has_diff"):
        refs.append(
            evidence_ref(
                "Commit diff",
                url=github_commit_url(repo_full_name, sha) if sha else None,
                kind="diff",
            )
        )
    return refs


def compare_evidence_refs(
    detail_a: dict, detail_b: dict, comparison: dict | None, repo_full_name: str
) -> list[dict[str, str | None]]:
    sha_a = detail_a.get("short_sha") or detail_a.get("sha", "")[:7]
    sha_b = detail_b.get("short_sha") or detail_b.get("sha", "")[:7]
    refs = [
        evidence_ref(
            f"Commit A {sha_a}",
            url=github_commit_url(repo_full_name, detail_a.get("sha", "")),
            kind="commit",
        ),
        evidence_ref(
            f"Commit B {sha_b}",
            url=github_commit_url(repo_full_name, detail_b.get("sha", "")),
            kind="commit",
        ),
        evidence_ref("Commit comparison", kind="compare"),
    ]
    if comparison and comparison.get("valid"):
        counts = comparison["counts"]
        refs.append(
            evidence_ref(
                f"{counts['overlap']} shared, {counts['only_a']} only A, {counts['only_b']} only B",
                kind="compare_stats",
            )
        )
        for path in (comparison.get("overlap") or [])[:3]:
            refs.append(
                evidence_ref(
                    path,
                    url=github_file_url(
                        repo_full_name, detail_a.get("sha", ""), path
                    ),
                    kind="file",
                )
            )
    return refs


def last_commit_author_evidence(
    sha: str | None, branch: str, repo_full_name: str
) -> list[dict[str, str | None]]:
    refs: list[dict[str, str | None]] = []
    if sha:
        refs.append(
            evidence_ref(
                f"Commit {sha[:7]} on {branch}",
                url=github_commit_url(repo_full_name, sha),
                kind="commit",
            )
        )
    refs.append(
        evidence_ref(
            f"Commit history ({branch})",
            url=github_repo_url(repo_full_name),
            kind="history",
        )
    )
    return refs


def previous_commit_evidence(
    sha: str | None, branch: str, repo_full_name: str
) -> list[dict[str, str | None]]:
    refs = last_commit_author_evidence(sha, branch, repo_full_name)
    if sha:
        refs[0] = evidence_ref(
            f"Previous commit {sha[:7]}",
            url=github_commit_url(repo_full_name, sha),
            kind="commit",
        )
    return refs


def repo_stats_evidence_refs(stats: dict) -> list[dict[str, str | None]]:
    repo = stats["repo"]
    branch = stats["branch"]
    refs = [
        evidence_ref(
            f"{stats['commit_count']} commits on {branch}",
            url=github_repo_url(repo),
            kind="stats",
        ),
        evidence_ref(
            f"{stats['contributor_count']} contributors",
            url=f"{github_repo_url(repo)}/graphs/contributors",
            kind="stats",
        ),
    ]
    for c in (stats.get("contributors") or [])[:3]:
        login = c.get("login", "")
        if login:
            refs.append(
                evidence_ref(
                    f"{login} ({c.get('contributions', 0)} commits)",
                    url=f"https://github.com/{login}",
                    kind="contributor",
                )
            )
    return refs


def repo_created_evidence(repo_full_name: str, created_at: str) -> list[dict[str, str | None]]:
    return [
        evidence_ref(
            "Repository metadata",
            url=github_repo_url(repo_full_name),
            kind="metadata",
        ),
        evidence_ref(f"Created {created_at}", kind="metadata"),
    ]


def file_churn_evidence(churn: dict, repo_full_name: str) -> list[dict[str, str | None]]:
    refs = [
        evidence_ref(
            f"{churn.get('commits_analyzed', 0)} commits analyzed",
            url=github_repo_url(repo_full_name),
            kind="churn",
        )
    ]
    for filename, _ in (churn.get("by_commit_count") or [])[:3]:
        refs.append(evidence_ref(filename, kind="file"))
    return refs


def ci_evidence(repo_full_name: str, runs: list[dict] | None = None) -> list[dict[str, str | None]]:
    refs = [
        evidence_ref(
            "GitHub Actions runs",
            url=github_actions_url(repo_full_name),
            kind="ci",
        )
    ]
    for run in (runs or [])[:2]:
        sha = run.get("head_sha") or ""
        if sha:
            refs.append(
                evidence_ref(
                    f"Workflow run {sha[:7]}",
                    url=github_commit_url(repo_full_name, sha),
                    kind="ci_run",
                )
            )
    return refs


def deployment_evidence(repo_full_name: str) -> list[dict[str, str | None]]:
    return [
        evidence_ref(
            "GitHub deployments",
            url=f"{github_repo_url(repo_full_name)}/deployments",
            kind="deployment",
        )
    ]


def release_evidence(repo_full_name: str) -> list[dict[str, str | None]]:
    return [
        evidence_ref(
            "GitHub releases",
            url=f"{github_repo_url(repo_full_name)}/releases",
            kind="release",
        )
    ]


def activity_overview_evidence(ctx: dict) -> list[dict[str, str | None]]:
    repo = ctx.get("repo", "")
    refs = [
        evidence_ref("Repository overview", url=github_repo_url(repo), kind="overview")
    ]
    if ctx.get("commits"):
        refs.append(evidence_ref("Recent commits", kind="history"))
    activity = ctx.get("repo_activity") or {}
    if activity.get("workflow_runs"):
        refs.extend(ci_evidence(repo, activity.get("workflow_runs")))
    if activity.get("deployments"):
        refs.extend(deployment_evidence(repo))
    if activity.get("releases"):
        refs.extend(release_evidence(repo))
    return refs


def recent_changes_evidence(ctx: dict) -> list[dict[str, str | None]]:
    repo = ctx.get("repo", "")
    refs = [evidence_ref("Recent repository activity", url=github_repo_url(repo))]
    activity = ctx.get("repo_activity") or {}
    if activity.get("events"):
        refs.append(evidence_ref("Repository events", kind="events"))
    if activity.get("workflow_runs"):
        refs.extend(ci_evidence(repo, activity.get("workflow_runs")))
    if ctx.get("commits"):
        refs.append(evidence_ref("Recent commits", kind="history"))
    return refs


def multi_compare_evidence_refs(
    details: list[dict],
    comparison: dict | None,
    repo_full_name: str,
) -> list[dict[str, str | None]]:
    refs = [evidence_ref(f"{len(details)}-commit comparison", kind="compare")]
    for detail in details[:5]:
        sha = detail.get("sha", "")
        short = detail.get("short_sha") or sha[:7]
        refs.append(
            evidence_ref(
                f"Commit {short}",
                url=github_commit_url(repo_full_name, sha),
                kind="commit",
            )
        )
    if comparison:
        repeated = comparison.get("repeatedly_touched") or {}
        if repeated:
            refs.append(
                evidence_ref(
                    f"{len(repeated)} files touched in multiple commits",
                    kind="compare_stats",
                )
            )
    return refs


def build_question_evidence(
    message: str,
    ctx: dict,
    repo_full_name: str,
) -> list[dict[str, str | None]]:
    """Lean, question-specific GitHub evidence — no generic file-tree noise."""
    from app.services.repo_context import (
        is_activity_overview_question,
        is_ci_question,
        is_commit_count_question,
        is_contributor_question,
        is_deployment_question,
        is_file_churn_question,
        is_last_commit_author_question,
        is_recent_changes_question,
        is_release_question,
        is_repo_created_question,
        needs_stack_inspection,
    )

    if is_last_commit_author_question(message):
        commits = ctx.get("commits") or []
        sha = (commits[0].get("sha") if commits else None) or None
        return last_commit_author_evidence(sha, ctx.get("branch", "main"), repo_full_name)

    if is_recent_changes_question(message):
        return recent_changes_evidence(ctx)

    if is_activity_overview_question(message):
        return activity_overview_evidence(ctx)

    if is_ci_question(message):
        activity = ctx.get("repo_activity") or {}
        return ci_evidence(repo_full_name, activity.get("workflow_runs"))

    if is_deployment_question(message):
        return deployment_evidence(repo_full_name)

    if is_release_question(message):
        return release_evidence(repo_full_name)

    if is_commit_count_question(message) or is_contributor_question(message):
        stats = ctx.get("repo_stats")
        if stats:
            return repo_stats_evidence_refs(stats)
        return [evidence_ref("GitHub commit history", url=github_repo_url(repo_full_name))]

    if is_file_churn_question(message):
        churn = ctx.get("file_churn") or {}
        return file_churn_evidence(churn, repo_full_name)

    if is_repo_created_question(message):
        created = (ctx.get("repo_meta") or {}).get("created_at", "")
        return repo_created_evidence(repo_full_name, created)

    if needs_stack_inspection(message):
        refs: list[dict[str, str | None]] = []
        if ctx.get("readme"):
            refs.append(evidence_ref("README", kind="readme"))
        config = ctx.get("config_files") or {}
        if "package.json" in config:
            refs.append(evidence_ref("package.json", kind="config"))
        for path in list((ctx.get("source_files") or {}).keys())[:4]:
            refs.append(
                evidence_ref(
                    path,
                    url=f"{github_repo_url(repo_full_name)}/blob/{ctx.get('branch', 'main')}/{path}",
                    kind="file",
                )
            )
        return refs or [evidence_ref("Repository source files", url=github_repo_url(repo_full_name))]

    commit_detail = ctx.get("commit_detail")
    if commit_detail:
        return commit_evidence_refs(commit_detail, repo_full_name)

    return [evidence_ref("GitHub repository", url=github_repo_url(repo_full_name))]
