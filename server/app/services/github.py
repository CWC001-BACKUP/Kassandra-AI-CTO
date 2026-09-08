"""GitHub API helpers for listing and inspecting repositories."""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _auth_headers(access_token: str) -> dict[str, str]:
    return {**GITHUB_HEADERS, "Authorization": f"Bearer {access_token}"}


async def _github_get(
    access_token: str,
    path: str,
    *,
    params: dict | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await client.get(
            f"https://api.github.com{path}",
            headers=_auth_headers(access_token),
            params=params,
        )


def _handle_response(response: httpx.Response, context: str) -> None:
    if response.status_code == 401:
        raise GitHubError(
            "GitHub token expired or invalid. Re-connect GitHub in Settings.",
            401,
        )
    if response.status_code == 404:
        raise GitHubError(f"{context} not found", 404)
    if response.status_code != 200:
        logger.warning("GitHub %s error: %s", context, response.text[:300])
        raise GitHubError(f"Failed to fetch {context} from GitHub", 502)


def _relative_time(iso_timestamp: str | None) -> str:
    if not iso_timestamp:
        return ""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        delta = datetime.now(dt.tzinfo) - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"
    except ValueError:
        return iso_timestamp


async def list_user_repos(access_token: str, *, per_page: int = 100) -> list[dict]:
    """List repositories the authenticated user can access."""
    repos: list[dict] = []
    page = 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            response = await client.get(
                "https://api.github.com/user/repos",
                headers=_auth_headers(access_token),
                params={
                    "per_page": per_page,
                    "page": page,
                    "sort": "updated",
                    "affiliation": "owner,collaborator,organization_member",
                },
            )
            _handle_response(response, "repositories")

            batch = response.json()
            if not batch:
                break

            for repo in batch:
                repos.append(
                    {
                        "id": repo["id"],
                        "full_name": repo["full_name"],
                        "name": repo["name"],
                        "owner": repo["owner"]["login"],
                        "html_url": repo["html_url"],
                        "description": repo.get("description"),
                        "private": repo.get("private", False),
                        "default_branch": repo.get("default_branch", "main"),
                        "language": repo.get("language"),
                        "updated_at": repo.get("updated_at"),
                    }
                )

            if len(batch) < per_page:
                break
            page += 1

    return repos


def _parse_link_last_page(link_header: str) -> int | None:
    match = re.search(r'page=(\d+)>;\s*rel="last"', link_header)
    return int(match.group(1)) if match else None


async def get_repo(access_token: str, full_name: str) -> dict:
    """Fetch a single repository by owner/repo slug."""
    response = await _github_get(access_token, f"/repos/{full_name}")
    _handle_response(response, f"repository '{full_name}'")

    repo = response.json()
    return {
        "id": repo["id"],
        "full_name": repo["full_name"],
        "name": repo["name"],
        "owner": repo["owner"]["login"],
        "html_url": repo["html_url"],
        "description": repo.get("description"),
        "private": repo.get("private", False),
        "default_branch": repo.get("default_branch", "main"),
        "language": repo.get("language"),
        "updated_at": repo.get("updated_at"),
        "created_at": repo.get("created_at"),
        "pushed_at": repo.get("pushed_at"),
        "size": repo.get("size"),
        "stargazers_count": repo.get("stargazers_count", 0),
        "forks_count": repo.get("forks_count", 0),
        "open_issues_count": repo.get("open_issues_count", 0),
        "watchers_count": repo.get("watchers_count", 0),
        "topics": repo.get("topics") or [],
        "license": (repo.get("license") or {}).get("spdx_id"),
        "archived": repo.get("archived", False),
        "disabled": repo.get("disabled", False),
    }


async def list_commit_shas(
    access_token: str,
    full_name: str,
    *,
    branch: str = "main",
    max_commits: int = 150,
    per_page: int = 100,
) -> list[str]:
    """Collect commit SHAs from a branch (paginated, capped)."""
    shas: list[str] = []
    page = 1

    while len(shas) < max_commits:
        response = await _github_get(
            access_token,
            f"/repos/{full_name}/commits",
            params={"sha": branch, "per_page": per_page, "page": page},
        )
        _handle_response(response, "commits")
        batch = response.json()
        if not batch:
            break
        for commit in batch:
            shas.append(commit["sha"])
            if len(shas) >= max_commits:
                break
        if len(batch) < per_page:
            break
        page += 1

    return shas


async def get_commit_file_stats(
    access_token: str,
    full_name: str,
    sha: str,
    *,
    include_patch: bool = False,
) -> list[dict]:
    """Return per-file change stats for a single commit."""
    response = await _github_get(
        access_token, f"/repos/{full_name}/commits/{sha}"
    )
    if response.status_code == 404:
        return []
    _handle_response(response, f"commit {sha}")
    commit = response.json()
    files: list[dict] = []
    for f in commit.get("files") or []:
        entry = {
            "filename": f["filename"],
            "status": f.get("status", "modified"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changes": f.get("changes", 0),
        }
        if include_patch and f.get("patch"):
            entry["patch"] = f["patch"][:3000]
        files.append(entry)
    return files


async def analyze_file_churn(
    access_token: str,
    full_name: str,
    *,
    branch: str = "main",
    max_commits: int = 150,
) -> dict:
    """Analyze which files change most often across commit history."""
    import asyncio
    from collections import defaultdict

    shas = await list_commit_shas(
        access_token, full_name, branch=branch, max_commits=max_commits
    )
    if not shas:
        return {
            "commits_analyzed": 0,
            "by_commit_count": [],
            "by_line_changes": [],
        }

    commit_counts: dict[str, int] = defaultdict(int)
    line_changes: dict[str, int] = defaultdict(int)
    sem = asyncio.Semaphore(8)

    async def _process(sha: str) -> None:
        async with sem:
            files = await get_commit_file_stats(access_token, full_name, sha)
            for f in files:
                name = f["filename"]
                commit_counts[name] += 1
                line_changes[name] += f.get("changes") or (
                    f.get("additions", 0) + f.get("deletions", 0)
                )

    await asyncio.gather(*[_process(sha) for sha in shas])

    by_commits = sorted(commit_counts.items(), key=lambda x: (-x[1], x[0]))[:20]
    by_lines = sorted(line_changes.items(), key=lambda x: (-x[1], x[0]))[:20]

    return {
        "commits_analyzed": len(shas),
        "by_commit_count": by_commits,
        "by_line_changes": by_lines,
    }


def _paths_match(candidate: str, target: str) -> bool:
    """Case-insensitive exact path match with ./ prefix normalization."""

    def norm(p: str) -> str:
        cleaned = p.strip().replace("\\", "/").lstrip("./")
        return cleaned.lower()

    return norm(candidate) == norm(target)


async def trace_file_history(
    access_token: str,
    full_name: str,
    file_path: str,
    *,
    branch: str = "main",
    max_commits: int = 200,
    symbol: str | None = None,
) -> dict:
    """Trace when a file (and optionally a symbol) first appeared in branch history."""
    import asyncio

    target = file_path.strip().replace("\\", "/").lstrip("./")
    shas = await list_commit_shas(
        access_token, full_name, branch=branch, max_commits=max_commits
    )
    if not shas:
        return {
            "found": False,
            "file_path": target,
            "branch": branch,
            "commits_analyzed": 0,
        }

    commit_meta = await list_commits(
        access_token, full_name, branch=branch, per_page=min(len(shas), max_commits)
    )
    meta_by_sha = {c["sha"]: c for c in commit_meta if c.get("sha")}

    introduction: dict | None = None
    last_change: dict | None = None
    symbol_intro: dict | None = None
    sem = asyncio.Semaphore(8)

    async def _inspect(sha: str) -> tuple[str, list[dict]]:
        async with sem:
            files = await get_commit_file_stats(
                access_token,
                full_name,
                sha,
                include_patch=bool(symbol),
            )
            return sha, files

    # Oldest → newest
    results = await asyncio.gather(*[_inspect(sha) for sha in reversed(shas)])

    for sha, files in results:
        file_entry = next(
            (f for f in files if _paths_match(f["filename"], target)),
            None,
        )
        if not file_entry:
            continue

        meta = meta_by_sha.get(sha, {})
        change = {
            "sha": sha,
            "short_sha": sha[:7],
            "status": file_entry.get("status", "modified"),
            "author": meta.get("author", "unknown"),
            "date": meta.get("date") or meta.get("time", ""),
            "message": meta.get("title", ""),
            "additions": file_entry.get("additions", 0),
            "deletions": file_entry.get("deletions", 0),
        }

        if introduction is None:
            introduction = change
        last_change = change

        if symbol and not symbol_intro:
            patch = file_entry.get("patch") or ""
            symbol_pattern = re.compile(
                rf"\b{re.escape(symbol)}\b",
                re.I,
            )
            if symbol_pattern.search(patch):
                symbol_intro = {**change, "symbol": symbol}

    return {
        "found": introduction is not None,
        "file_path": target,
        "branch": branch,
        "commits_analyzed": len(shas),
        "introduction": introduction,
        "last_change": last_change,
        "symbol_introduction": symbol_intro,
        "symbol": symbol,
    }


async def list_pull_requests(
    access_token: str,
    full_name: str,
    *,
    state: str = "all",
    per_page: int = 20,
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/pulls",
        params={"state": state, "per_page": per_page, "sort": "updated"},
    )
    _handle_response(response, "pull requests")

    items: list[dict] = []
    for pr in response.json():
        items.append(
            {
                "id": pr["id"],
                "type": "pr",
                "number": pr["number"],
                "title": pr["title"],
                "author": pr["user"]["login"],
                "branch": pr["head"]["ref"],
                "status": pr["state"] if pr["state"] == "open" else "merged",
                "merged": pr.get("merged_at") is not None,
                "files": 0,
                "additions": 0,
                "deletions": 0,
                "html_url": pr["html_url"],
                "time": _relative_time(pr.get("updated_at")),
                "timestamp": pr.get("updated_at"),
            }
        )
    return items


async def count_commits(
    access_token: str,
    full_name: str,
    *,
    branch: str = "main",
    per_page: int = 100,
) -> int:
    """Count commits on a branch using GitHub pagination headers (2 requests max)."""
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/commits",
        params={"sha": branch, "per_page": per_page, "page": 1},
    )
    _handle_response(response, "commits")

    first_page = response.json()
    if not first_page:
        return 0

    link = response.headers.get("Link", "")
    last_page = _parse_link_last_page(link)
    if not last_page or last_page == 1:
        return len(first_page)

    response = await _github_get(
        access_token,
        f"/repos/{full_name}/commits",
        params={"sha": branch, "per_page": per_page, "page": last_page},
    )
    _handle_response(response, "commits")
    last_batch = response.json()
    return (last_page - 1) * per_page + len(last_batch)


async def list_contributors(
    access_token: str,
    full_name: str,
    *,
    per_page: int = 100,
) -> list[dict]:
    """List repository contributors with contribution counts."""
    contributors: list[dict] = []
    page = 1

    while True:
        response = await _github_get(
            access_token,
            f"/repos/{full_name}/contributors",
            params={"per_page": per_page, "page": page, "anon": "true"},
        )
        if response.status_code == 404:
            return []
        _handle_response(response, "contributors")

        batch = response.json()
        if not batch:
            break

        for contributor in batch:
            contributors.append(
                {
                    "login": contributor.get("login") or "anonymous",
                    "contributions": contributor.get("contributions", 0),
                    "html_url": contributor.get("html_url"),
                    "type": contributor.get("type", "User"),
                }
            )

        if len(batch) < per_page:
            break
        page += 1

    return contributors


async def list_commits(
    access_token: str,
    full_name: str,
    *,
    branch: str = "main",
    per_page: int = 20,
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/commits",
        params={"sha": branch, "per_page": per_page},
    )
    _handle_response(response, "commits")

    items: list[dict] = []
    for commit in response.json():
        items.append(_commit_list_item(commit, branch))
    return items


def _commit_list_item(commit: dict, branch: str) -> dict:
    message = commit["commit"]["message"].split("\n")[0]
    author_login = (commit.get("author") or {}).get("login")
    author_name = commit["commit"]["author"]["name"]
    author = author_login or author_name or "unknown"
    date = commit["commit"]["author"].get("date", "")
    return {
        "id": commit["sha"],
        "sha": commit["sha"],
        "type": "commit",
        "title": message,
        "author": author,
        "branch": branch,
        "status": "committed",
        "files": len(commit.get("files") or []),
        "additions": 0,
        "deletions": 0,
        "html_url": commit.get("html_url"),
        "time": _relative_time(date),
        "timestamp": date,
        "date": date,
    }


async def get_oldest_commit_on_branch(
    access_token: str,
    full_name: str,
    *,
    branch: str = "main",
    per_page: int = 100,
) -> dict | None:
    """Return the oldest commit on a branch by walking to the last pagination page."""
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/commits",
        params={"sha": branch, "per_page": per_page, "page": 1},
    )
    _handle_response(response, "commits")

    first_page = response.json()
    if not first_page:
        return None

    link = response.headers.get("Link", "")
    last_page = _parse_link_last_page(link)
    if not last_page or last_page == 1:
        return _commit_list_item(first_page[-1], branch)

    response = await _github_get(
        access_token,
        f"/repos/{full_name}/commits",
        params={"sha": branch, "per_page": per_page, "page": last_page},
    )
    _handle_response(response, "commits")
    last_batch = response.json()
    if not last_batch:
        return None
    return _commit_list_item(last_batch[-1], branch)


async def get_repo_languages(access_token: str, full_name: str) -> dict[str, int]:
    response = await _github_get(access_token, f"/repos/{full_name}/languages")
    if response.status_code == 404:
        return {}
    _handle_response(response, "languages")
    return response.json()


async def get_readme(access_token: str, full_name: str) -> str | None:
    response = await _github_get(access_token, f"/repos/{full_name}/readme")
    if response.status_code == 404:
        return None
    _handle_response(response, "README")
    data = response.json()
    content = data.get("content", "")
    if data.get("encoding") == "base64" and content:
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return content or None


async def list_root_files(access_token: str, full_name: str) -> list[str]:
    items = await list_directory(access_token, full_name, "")
    return [item["name"] for item in items if item.get("type") == "file"]


async def list_directory(
    access_token: str, full_name: str, path: str = ""
) -> list[dict]:
    """List files and directories at a repository path."""
    api_path = f"/repos/{full_name}/contents/{path}" if path else f"/repos/{full_name}/contents/"
    response = await _github_get(access_token, api_path)
    if response.status_code == 404:
        return []
    _handle_response(response, f"directory '{path or 'root'}'")
    data = response.json()
    if isinstance(data, dict):
        return []
    return [
        {
            "name": item["name"],
            "path": item["path"],
            "type": item["type"],
            "size": item.get("size", 0),
        }
        for item in data
    ]


async def build_repo_tree(
    access_token: str,
    full_name: str,
    *,
    path: str = "",
    depth: int = 0,
    max_depth: int = 3,
    max_entries: int = 120,
) -> list[str]:
    """Build a flat list of repository paths up to max_depth."""
    entries: list[str] = []

    async def _walk(current_path: str, current_depth: int) -> None:
        if current_depth > max_depth or len(entries) >= max_entries:
            return
        items = await list_directory(access_token, full_name, current_path)
        for item in items:
            if len(entries) >= max_entries:
                break
            display = item["path"]
            prefix = "  " * current_depth
            if item["type"] == "dir":
                entries.append(f"{prefix}{display}/")
                await _walk(item["path"], current_depth + 1)
            else:
                entries.append(f"{prefix}{display}")

    await _walk(path, depth)
    return entries


async def list_issues(
    access_token: str,
    full_name: str,
    *,
    state: str = "open",
    per_page: int = 10,
) -> list[dict]:
    response = await _github_get(
        access_token,
        f"/repos/{full_name}/issues",
        params={"state": state, "per_page": per_page, "sort": "updated"},
    )
    _handle_response(response, "issues")
    items: list[dict] = []
    for issue in response.json():
        if "pull_request" in issue:
            continue  # skip PRs in issues endpoint
        items.append(
            {
                "number": issue["number"],
                "title": issue["title"],
                "author": issue["user"]["login"],
                "state": issue["state"],
                "created_at": issue.get("created_at"),
            }
        )
    return items


async def get_commit_detail(
    access_token: str, full_name: str, sha: str
) -> dict:
    response = await _github_get(
        access_token, f"/repos/{full_name}/commits/{sha}"
    )
    _handle_response(response, f"commit {sha}")
    commit = response.json()
    author_login = (commit.get("author") or {}).get("login")
    author_name = commit["commit"]["author"]["name"]
    all_files = commit.get("files") or []
    files: list[dict] = []
    patches: list[str] = []
    all_filenames: list[str] = []
    for i, f in enumerate(all_files):
        path = f["filename"]
        all_filenames.append(path)
        entry = {
            "filename": path,
            "status": f.get("status", "modified"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changes": f.get("changes", 0),
        }
        patch = f.get("patch")
        if patch:
            entry["patch"] = patch[:2500]
            if i < 25:
                patches.append(f"--- {path} ---\n{patch[:2500]}")
        files.append(entry)

    stats = commit.get("stats") or {}
    return {
        "sha": commit["sha"],
        "short_sha": commit["sha"][:7],
        "title": commit["commit"]["message"].split("\n")[0],
        "full_message": commit["commit"]["message"],
        "author": author_login or author_name or "unknown",
        "date": commit["commit"]["author"].get("date"),
        "files": files,
        "all_filenames": all_filenames,
        "file_count": len(all_files),
        "additions": stats.get("additions", 0),
        "deletions": stats.get("deletions", 0),
        "diff_excerpt": "\n\n".join(patches)[:12000],
        "has_diff": bool(patches),
        "parent_shas": [p["sha"] for p in commit.get("parents") or []],
    }


async def get_file_content(
    access_token: str, full_name: str, path: str
) -> str | None:
    response = await _github_get(access_token, f"/repos/{full_name}/contents/{path}")
    if response.status_code == 404:
        return None
    _handle_response(response, path)
    data = response.json()
    if data.get("type") != "file":
        return None
    content = data.get("content", "")
    if data.get("encoding") == "base64" and content:
        return base64.b64decode(content).decode("utf-8", errors="replace")[:8000]
    return (content or "")[:8000]


async def create_repo_webhook(
    access_token: str,
    full_name: str,
    webhook_url: str,
    secret: str,
) -> int | None:
    """Register a GitHub webhook for push and pull_request events."""
    payload = {
        "name": "web",
        "active": True,
        "events": ["push", "pull_request"],
        "config": {
            "url": webhook_url,
            "content_type": "json",
            "secret": secret,
            "insecure_ssl": "0",
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://api.github.com/repos/{full_name}/hooks",
            headers=_auth_headers(access_token),
            json=payload,
        )

    if response.status_code in {201, 200}:
        return response.json().get("id")
    logger.warning("Webhook creation failed for %s: %s", full_name, response.text[:300])
    return None
