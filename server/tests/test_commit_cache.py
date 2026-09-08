import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.commit_cache import (
    get_cached_commit_detail,
    load_commit_cache,
    preload_recent_commits,
    store_commit_details,
)


def _detail(sha: str) -> dict:
    return {
        "sha": sha,
        "short_sha": sha[:7],
        "title": "test",
        "author": "dev",
        "date": "2026-01-01",
        "files": [],
        "all_filenames": [],
        "file_count": 0,
        "has_diff": False,
    }


def test_store_and_load_commit_cache_roundtrip() -> None:
    sha = "a" * 40
    provider = MagicMock()
    stored: dict[str, str] = {}

    def _set_reference(key: str, body: str, metadata: dict | None = None) -> None:
        stored[key] = body

    def _get_reference(key: str) -> dict | None:
        body = stored.get(key)
        return {"body": body} if body else None

    provider.set_reference.side_effect = _set_reference
    provider.get_reference.side_effect = _get_reference

    with patch("app.services.commit_cache.get_memory_provider", return_value=provider):
        store_commit_details("acme/api", [_detail(sha)], branch="main")
        cached = get_cached_commit_detail("acme/api", sha[:7])
        cache = load_commit_cache("acme/api")

    assert cached is not None
    assert cached["sha"] == sha
    assert cache["branch"] == "main"


@pytest.mark.asyncio
async def test_preload_recent_commits_skips_github_when_cached() -> None:
    sha = "b" * 40
    provider = MagicMock()
    provider.get_reference.return_value = {
        "body": json.dumps({"commits": {sha: _detail(sha)}, "order": [sha]})
    }

    with (
        patch("app.services.commit_cache.get_memory_provider", return_value=provider),
        patch(
            "app.services.github.list_commits",
            new_callable=AsyncMock,
            return_value=[{"sha": sha}],
        ) as list_mock,
        patch(
            "app.services.github.get_commit_detail",
            new_callable=AsyncMock,
        ) as detail_mock,
    ):
        count = await preload_recent_commits("token", "acme/api", branch="main", count=1)

    assert count == 1
    detail_mock.assert_not_called()
    list_mock.assert_awaited_once()
