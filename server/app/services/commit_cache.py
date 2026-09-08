"""Cached commit details from analysis — fewer GitHub round-trips during chat."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from app.services.memory import get_memory_provider

logger = logging.getLogger(__name__)

CACHE_KEY = "commit_cache"
MAX_CACHED = 20
DEFAULT_PRELOAD_COUNT = 10


def _empty_cache() -> dict:
    return {"commits": {}, "fetched_at": None, "branch": None}


def load_commit_cache(repo_full_name: str) -> dict:
    memory = get_memory_provider(repo_full_name)
    ref = memory.get_reference(CACHE_KEY)
    if not ref:
        return _empty_cache()
    try:
        data = json.loads(ref.get("body") or "{}")
    except json.JSONDecodeError:
        return _empty_cache()
    if not isinstance(data.get("commits"), dict):
        data["commits"] = {}
    return data


def save_commit_cache(repo_full_name: str, cache: dict) -> None:
    memory = get_memory_provider(repo_full_name)
    memory.set_reference(
        CACHE_KEY,
        json.dumps(cache),
        metadata={"type": "commit_cache", "repo": repo_full_name},
    )


def get_cached_commit_detail(repo_full_name: str, sha: str) -> dict | None:
    if not sha:
        return None
    commits = load_commit_cache(repo_full_name).get("commits") or {}
    if sha in commits:
        return commits[sha]
    prefix = sha[:7].lower()
    for full_sha, detail in commits.items():
        if full_sha.lower().startswith(prefix) or full_sha.lower()[:7] == prefix:
            return detail
    return None


def store_commit_details(
    repo_full_name: str,
    details: list[dict],
    *,
    branch: str | None = None,
) -> None:
    cache = load_commit_cache(repo_full_name)
    commits: dict[str, dict] = dict(cache.get("commits") or {})
    order: list[str] = list(cache.get("order") or [])

    for detail in details:
        sha = detail.get("sha")
        if not sha:
            continue
        commits[sha] = detail
        if sha in order:
            order.remove(sha)
        order.insert(0, sha)

    while len(order) > MAX_CACHED:
        drop = order.pop()
        commits.pop(drop, None)

    cache["commits"] = commits
    cache["order"] = order
    cache["fetched_at"] = datetime.now(UTC).isoformat()
    if branch:
        cache["branch"] = branch
    save_commit_cache(repo_full_name, cache)


async def fetch_commit_details_cached(
    access_token: str,
    repo_full_name: str,
    shas: list[str],
) -> list[dict]:
    """Return commit details, using Sibyl cache when SHAs were preloaded at analysis."""
    from app.services.github import get_commit_detail

    results: list[dict | None] = [None] * len(shas)
    to_fetch: list[tuple[int, str]] = []

    for index, sha in enumerate(shas):
        cached = get_cached_commit_detail(repo_full_name, sha)
        if cached:
            results[index] = cached
        else:
            to_fetch.append((index, sha))

    if to_fetch:
        fetched = await asyncio.gather(
            *[
                get_commit_detail(access_token, repo_full_name, sha)
                for _, sha in to_fetch
            ]
        )
        store_commit_details(repo_full_name, list(fetched))
        for (index, _), detail in zip(to_fetch, fetched, strict=True):
            results[index] = detail

    return [detail for detail in results if detail is not None]


async def preload_recent_commits(
    access_token: str,
    repo_full_name: str,
    *,
    branch: str = "main",
    count: int = DEFAULT_PRELOAD_COUNT,
) -> int:
    """Fetch and cache recent commit details during repository analysis."""
    from app.services.github import get_commit_detail, list_commits

    per_page = min(max(count, 2), MAX_CACHED)
    commits = await list_commits(
        access_token,
        repo_full_name,
        branch=branch,
        per_page=per_page,
    )
    shas = [c.get("sha") or str(c.get("id", "")) for c in commits[:count]]
    shas = [sha for sha in shas if sha]
    if not shas:
        return 0

    uncached = [sha for sha in shas if not get_cached_commit_detail(repo_full_name, sha)]
    if not uncached:
        return len(shas)

    details = await asyncio.gather(
        *[get_commit_detail(access_token, repo_full_name, sha) for sha in uncached]
    )
    store_commit_details(repo_full_name, list(details), branch=branch)
    logger.info("Preloaded %d commit(s) for %s", len(details), repo_full_name)
    return len(shas)
