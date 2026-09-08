"""GitHub repository activity — CI/CD, deployments, releases, events."""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.services.github import (
    GitHubError,
    _auth_headers,
    _github_get,
    _handle_response,
    _relative_time,
)

logger = logging.getLogger(__name__)


async def _safe(coro, default=None):
    try:
        return await coro
    except GitHubError as exc:
        if exc.status_code in {403, 404}:
            logger.info("GitHub activity skipped: %s", exc.message)
            return default if default is not None else []
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("GitHub activity fetch failed: %s", exc)
        return default if default is not None else []


async def list_workflows(access_token: str, full_name: str) -> list[dict]:
    response = await _github_get(
        access_token, f"/repos/{full_name}/actions/workflows", params={"per_page": 30}
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "workflows")
    return [
        {
            "id": w["id"],
            "name": w["name"],
            "path": w.get("path"),
            "state": w.get("state"),
            "html_url": w.get("html_url"),
        }
        for w in response.json().get("workflows", [])
    ]


async def list_workflow_runs(
    access_token: str,
    full_name: str,
    *,
    branch: str | None = None,
    per_page: int = 15,
) -> list[dict]:
    params: dict = {"per_page": per_page}
    if branch:
        params["branch"] = branch
    response = await _github_get(
        access_token, f"/repos/{full_name}/actions/runs", params=params
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "workflow runs")
    runs = []
    for run in response.json().get("workflow_runs", []):
        runs.append(
            {
                "id": run["id"],
                "name": run.get("name") or run.get("display_title", "workflow"),
                "workflow": (run.get("path") or "").replace(".github/workflows/", ""),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "branch": run.get("head_branch"),
                "event": run.get("event"),
                "actor": (run.get("actor") or {}).get("login"),
                "head_sha": (run.get("head_sha") or "")[:7],
                "html_url": run.get("html_url"),
                "created_at": run.get("created_at"),
                "updated_at": run.get("updated_at"),
                "time": _relative_time(run.get("updated_at")),
            }
        )
    return runs


async def list_workflow_jobs(
    access_token: str, full_name: str, run_id: int
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/actions/runs/{run_id}/jobs",
        params={"per_page": 20},
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "workflow jobs")
    jobs = []
    for job in response.json().get("jobs", []):
        jobs.append(
            {
                "id": job["id"],
                "name": job["name"],
                "status": job.get("status"),
                "conclusion": job.get("conclusion"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "html_url": job.get("html_url"),
                "steps": [
                    {
                        "name": s.get("name"),
                        "status": s.get("status"),
                        "conclusion": s.get("conclusion"),
                        "number": s.get("number"),
                    }
                    for s in (job.get("steps") or [])
                ],
            }
        )
    return jobs


async def get_job_log_excerpt(
    access_token: str,
    full_name: str,
    job_id: int,
    *,
    max_chars: int = 5000,
) -> str:
    url = f"https://api.github.com/repos/{full_name}/actions/jobs/{job_id}/logs"
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url, headers=_auth_headers(access_token))
        if response.status_code != 200:
            return ""
        text = response.text
        if len(text) > max_chars:
            return "…\n" + text[-max_chars:]
        return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch job log %s: %s", job_id, exc)
        return ""


async def list_deployments(
    access_token: str, full_name: str, *, per_page: int = 15
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/deployments",
        params={"per_page": per_page},
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "deployments")
    return [
        {
            "id": d["id"],
            "sha": (d.get("sha") or "")[:7],
            "ref": d.get("ref"),
            "environment": d.get("environment"),
            "description": d.get("description"),
            "creator": (d.get("creator") or {}).get("login"),
            "created_at": d.get("created_at"),
            "time": _relative_time(d.get("created_at")),
        }
        for d in response.json()
    ]


async def list_deployment_statuses(
    access_token: str, full_name: str, deployment_id: int
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/deployments/{deployment_id}/statuses",
        params={"per_page": 5},
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "deployment statuses")
    return [
        {
            "state": s.get("state"),
            "description": s.get("description"),
            "environment": s.get("environment"),
            "target_url": s.get("target_url"),
            "created_at": s.get("created_at"),
            "time": _relative_time(s.get("created_at")),
        }
        for s in response.json()
    ]


async def list_releases(
    access_token: str, full_name: str, *, per_page: int = 15
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/releases",
        params={"per_page": per_page},
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "releases")
    return [
        {
            "id": r["id"],
            "tag": r.get("tag_name"),
            "name": r.get("name"),
            "author": (r.get("author") or {}).get("login"),
            "draft": r.get("draft", False),
            "prerelease": r.get("prerelease", False),
            "created_at": r.get("created_at"),
            "published_at": r.get("published_at"),
            "body": (r.get("body") or "")[:500],
            "html_url": r.get("html_url"),
            "time": _relative_time(r.get("published_at") or r.get("created_at")),
        }
        for r in response.json()
    ]


async def list_branches(
    access_token: str, full_name: str, *, per_page: int = 30
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/branches",
        params={"per_page": per_page},
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "branches")
    return [
        {
            "name": b["name"],
            "sha": (b.get("commit") or {}).get("sha", "")[:7],
            "protected": b.get("protected", False),
        }
        for b in response.json()
    ]


async def list_tags(
    access_token: str, full_name: str, *, per_page: int = 20
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/tags",
        params={"per_page": per_page},
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "tags")
    return [
        {
            "name": t["name"],
            "sha": (t.get("commit") or {}).get("sha", "")[:7],
        }
        for t in response.json()
    ]


async def list_repo_events(
    access_token: str, full_name: str, *, per_page: int = 30
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/events",
        params={"per_page": per_page},
    )
    if response.status_code == 404:
        return []
    _handle_response(response, "repository events")
    events = []
    for event in response.json():
        actor = (event.get("actor") or {}).get("login", "unknown")
        payload = event.get("payload") or {}
        summary = event.get("type", "Event")
        if event["type"] == "PushEvent":
            ref = payload.get("ref", "").replace("refs/heads/", "")
            count = len(payload.get("commits") or [])
            summary = f"Push to {ref} ({count} commits)"
        elif event["type"] == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request") or {}
            summary = f"PR #{pr.get('number')} {action}: {pr.get('title', '')}"
        elif event["type"] == "IssuesEvent":
            action = payload.get("action", "")
            issue = payload.get("issue") or {}
            summary = f"Issue #{issue.get('number')} {action}: {issue.get('title', '')}"
        elif event["type"] == "CreateEvent":
            ref_type = payload.get("ref_type", "")
            ref = payload.get("ref", "")
            summary = f"Created {ref_type} {ref}"
        elif event["type"] == "DeleteEvent":
            ref_type = payload.get("ref_type", "")
            ref = payload.get("ref", "")
            summary = f"Deleted {ref_type} {ref}"
        elif event["type"] == "ReleaseEvent":
            action = payload.get("action", "")
            release = payload.get("release") or {}
            summary = f"Release {action}: {release.get('tag_name', '')}"
        elif event["type"] == "DeploymentStatusEvent":
            state = (payload.get("deployment_status") or {}).get("state", "")
            env = (payload.get("deployment") or {}).get("environment", "")
            summary = f"Deployment to {env}: {state}"
        elif event["type"] == "WorkflowRunEvent":
            action = payload.get("action", "")
            run = payload.get("workflow_run") or {}
            summary = (
                f"Workflow {action}: {run.get('name', '')} "
                f"[{run.get('conclusion') or run.get('status')}]"
            )

        events.append(
            {
                "type": event.get("type"),
                "summary": summary,
                "actor": actor,
                "created_at": event.get("created_at"),
                "time": _relative_time(event.get("created_at")),
            }
        )
    return events


async def list_environments(access_token: str, full_name: str) -> list[dict]:
    response = await _github_get(
        access_token, f"/repos/{full_name}/environments"
    )
    if response.status_code in {404, 403}:
        return []
    _handle_response(response, "environments")
    return [
        {
            "name": e.get("name"),
            "html_url": e.get("html_url"),
        }
        for e in response.json().get("environments", [])
    ]


async def _enrich_deployments(
    access_token: str, full_name: str, deployments: list[dict]
) -> list[dict]:
    enriched = []
    for dep in deployments[:8]:
        statuses = await _safe(
            list_deployment_statuses(access_token, full_name, dep["id"]), []
        )
        latest = statuses[0] if statuses else {}
        enriched.append({**dep, "latest_status": latest, "statuses": statuses})
    return enriched


async def _enrich_failed_runs(
    access_token: str, full_name: str, runs: list[dict]
) -> list[dict]:
    enriched = []
    failed = [
        r
        for r in runs
        if r.get("conclusion") in {"failure", "cancelled", "timed_out", "action_required"}
        or r.get("status") == "in_progress"
    ][:4]

    for run in failed:
        jobs = await _safe(list_workflow_jobs(access_token, full_name, run["id"]), [])
        job_logs: list[dict] = []
        for job in jobs:
            if job.get("conclusion") in {"failure", "cancelled"} or job.get("status") == "in_progress":
                log = await get_job_log_excerpt(access_token, full_name, job["id"])
                if log:
                    job_logs.append(
                        {
                            "job_name": job["name"],
                            "conclusion": job.get("conclusion"),
                            "log_excerpt": log,
                        }
                    )
                if len(job_logs) >= 2:
                    break
        enriched.append({**run, "jobs": jobs, "job_logs": job_logs})
    return enriched


async def gather_repository_activity(
    access_token: str,
    full_name: str,
    *,
    branch: str = "main",
) -> dict:
    """Fetch comprehensive repository activity from GitHub."""
    (
        workflows,
        workflow_runs,
        deployments,
        releases,
        branches,
        tags,
        events,
        environments,
    ) = await asyncio.gather(
        _safe(list_workflows(access_token, full_name)),
        _safe(list_workflow_runs(access_token, full_name, branch=branch)),
        _safe(list_deployments(access_token, full_name)),
        _safe(list_releases(access_token, full_name)),
        _safe(list_branches(access_token, full_name)),
        _safe(list_tags(access_token, full_name)),
        _safe(list_repo_events(access_token, full_name)),
        _safe(list_environments(access_token, full_name)),
    )

    deployments_enriched, failed_runs = await asyncio.gather(
        _enrich_deployments(access_token, full_name, deployments),
        _enrich_failed_runs(access_token, full_name, workflow_runs),
    )

    return {
        "workflows": workflows,
        "workflow_runs": workflow_runs,
        "failed_runs": failed_runs,
        "deployments": deployments_enriched,
        "releases": releases,
        "branches": branches,
        "tags": tags,
        "events": events,
        "environments": environments,
    }


def format_workflow_runs_block(runs: list[dict]) -> str:
    if not runs:
        return "No GitHub Actions workflow runs found."
    lines = []
    for r in runs[:12]:
        conclusion = r.get("conclusion") or r.get("status") or "unknown"
        lines.append(
            f"• {r.get('name')} on {r.get('branch')} — {conclusion} "
            f"({r.get('time')}) by {r.get('actor', 'unknown')} "
            f"[{r.get('head_sha')}]"
        )
    return "\n".join(lines)


def format_deployments_block(deployments: list[dict]) -> str:
    if not deployments:
        return "No deployments recorded on GitHub."
    lines = []
    for d in deployments[:10]:
        status = d.get("latest_status") or {}
        state = status.get("state", "unknown")
        lines.append(
            f"• {d.get('environment')} — {state} "
            f"(ref {d.get('ref')}, sha {d.get('sha')}) "
            f"by {d.get('creator', 'unknown')} ({d.get('time')})"
        )
        if status.get("description"):
            lines.append(f"  Status: {status['description']}")
        if status.get("target_url"):
            lines.append(f"  URL: {status['target_url']}")
    return "\n".join(lines)


def format_releases_block(releases: list[dict]) -> str:
    if not releases:
        return "No releases found."
    lines = []
    for r in releases[:10]:
        tag = r.get("tag") or r.get("name")
        lines.append(
            f"• {tag} — {r.get('name', '')} by {r.get('author', 'unknown')} "
            f"({r.get('time')})"
            + (" [draft]" if r.get("draft") else "")
            + (" [pre-release]" if r.get("prerelease") else "")
        )
        if r.get("body"):
            lines.append(f"  {r['body'][:200]}")
    return "\n".join(lines)


def format_events_block(events: list[dict]) -> str:
    if not events:
        return "No recent repository events."
    lines = []
    for e in events[:20]:
        lines.append(
            f"• [{e.get('type')}] {e.get('summary')} by {e.get('actor')} ({e.get('time')})"
        )
    return "\n".join(lines)


def format_ci_logs_block(failed_runs: list[dict]) -> str:
    if not failed_runs:
        return "No recent failed or in-progress CI runs with logs."
    parts = []
    for run in failed_runs[:3]:
        parts.append(
            f"Run: {run.get('name')} [{run.get('conclusion') or run.get('status')}] "
            f"on {run.get('branch')} ({run.get('time')})"
        )
        for jl in run.get("job_logs") or []:
            parts.append(f"Job: {jl['job_name']} ({jl.get('conclusion')})")
            parts.append(jl.get("log_excerpt", "")[:3000])
        parts.append("")
    return "\n".join(parts).strip()


def format_activity_for_llm(activity: dict) -> str:
    sections = []

    workflows = activity.get("workflows") or []
    if workflows:
        names = ", ".join(w["name"] for w in workflows[:15])
        sections.append(f"Configured workflows: {names}")

    sections.append(
        f"Recent CI/CD runs:\n{format_workflow_runs_block(activity.get('workflow_runs') or [])}"
    )

    logs = format_ci_logs_block(activity.get("failed_runs") or [])
    if logs and "No recent failed" not in logs:
        sections.append(f"CI/CD logs (failed or active runs):\n{logs}")

    sections.append(
        f"Deployments:\n{format_deployments_block(activity.get('deployments') or [])}"
    )

    envs = activity.get("environments") or []
    if envs:
        sections.append(
            "Deployment environments: " + ", ".join(e["name"] for e in envs)
        )

    sections.append(
        f"Releases:\n{format_releases_block(activity.get('releases') or [])}"
    )

    branches = activity.get("branches") or []
    if branches:
        branch_names = ", ".join(b["name"] for b in branches[:20])
        sections.append(f"Branches ({len(branches)}): {branch_names}")

    tags = activity.get("tags") or []
    if tags:
        tag_names = ", ".join(t["name"] for t in tags[:15])
        sections.append(f"Tags: {tag_names}")

    sections.append(
        f"Repository activity feed:\n{format_events_block(activity.get('events') or [])}"
    )

    return "\n\n".join(sections)


def activity_evidence_sources(activity: dict) -> list[str]:
    sources = []
    if activity.get("workflow_runs"):
        sources.append("GitHub Actions runs")
    if activity.get("failed_runs"):
        sources.append("CI/CD logs")
    if activity.get("deployments"):
        sources.append("Deployments")
    if activity.get("releases"):
        sources.append("Releases")
    if activity.get("events"):
        sources.append("Repository events")
    if activity.get("branches"):
        sources.append("Branches")
    return sources
