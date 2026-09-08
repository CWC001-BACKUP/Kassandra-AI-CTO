#!/usr/bin/env python3
"""Simulate AI CTO behavior with Sibyl memory ON vs OFF.

Demonstrates that without Sibyl, Kassandra cannot fulfill the AI CTO role —
institutional decisions, incidents, and architecture rationale live in memory,
not in GitHub evidence alone.

Run from server/:
    python -m scripts.sibyl_simulation
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

# Ensure server root is on path when run as script
_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from app.models import Project, User
from app.services.chat import process_chat_message
from app.services.memory import get_memory_provider

TENANT = "simulation/acme-api"

CTO_QUESTIONS = [
    (
        "Why did we choose PostgreSQL over MongoDB?",
        ["PostgreSQL", "ACID", "relational"],
        "architecture decision",
    ),
    (
        "What caused the March 2026 outage and how did we fix it?",
        ["Redis", "connection pool", "outage"],
        "incident postmortem",
    ),
    (
        "What is our mobile-first requirement for the vendor dashboard?",
        ["mobile", "vendor dashboard", "mobile-first"],
        "product/engineering policy",
    ),
]

MINIMAL_REPO_CTX = {
    "repo": TENANT,
    "branch": "main",
    "commits": [
        {
            "sha": "deadbeef",
            "title": "chore: bump deps",
            "author": "dev",
            "date": "2026-08-01",
        }
    ],
    "pull_requests": [],
    "evidence_sources": ["commit history"],
    "formatted": "Repository: simulation/acme-api\nRecent commits: 1\nNo architecture docs in repo evidence.",
}


def _make_user() -> User:
    return User(
        id="sim-user",
        email="sim@example.com",
        full_name="Simulation User",
        github_username="simuser",
        github_access_token="gh-sim-token",
        is_verified=True,
    )


def _make_project() -> Project:
    return Project(
        id="sim-proj",
        user_id="sim-user",
        repo_full_name=TENANT,
        repo_url=f"https://github.com/{TENANT}",
        default_branch="main",
        is_active=True,
    )


def _seed_sibyl_memory(data_dir: Path) -> None:
    """Populate Sibyl with institutional knowledge a CTO must recall."""
    from app.config import get_settings
    from app.services import memory as memory_module

    memory_module._provider_cache.clear()
    get_settings.cache_clear()

    with patch.object(get_settings(), "sibyl_data_dir", str(data_dir)):
        memory = get_memory_provider(TENANT)

        memory.remember(
            "architecture",
            "database_choice",
            {
                "decision": "PostgreSQL over MongoDB",
                "rationale": (
                    "We need ACID transactions for billing and vendor payouts. "
                    "PostgreSQL gives us relational integrity; MongoDB was rejected "
                    "after a spike showed inconsistent payout state under concurrent writes."
                ),
                "decided_by": "engineering leadership",
                "date": "2025-11-12",
            },
        )

        memory.remember(
            "incident",
            "march_2026_outage",
            {
                "title": "March 2026 production outage",
                "root_cause": "Redis connection pool exhaustion under webhook burst",
                "resolution": (
                    "Increased pool size from 10 to 50, added circuit breaker on "
                    "GitHub webhook handler, deployed hotfix commit a1b2c3d."
                ),
                "duration_minutes": 47,
                "severity": "P1",
            },
        )

        memory.remember(
            "product",
            "vendor_dashboard_mobile",
            {
                "requirement": "Vendor dashboard must be mobile-first",
                "rationale": (
                    "68% of vendors access the dashboard from mobile devices during "
                    "field operations. All new vendor UI work must pass mobile viewport QA."
                ),
                "recorded": "2026-01-08",
            },
        )

        memory.save_context(
            inputs={"event": "simulation_seed", "repo": TENANT},
            outputs={"summary": "Seeded institutional memory for CTO simulation"},
        )

    memory_module._provider_cache.clear()


async def _run_question(
    user: User,
    project: Project,
    question: str,
    *,
    sibyl_enabled: bool,
    data_dir: Path,
) -> dict:
    from app.config import get_settings
    from app.services import memory as memory_module

    memory_module._provider_cache.clear()
    get_settings.cache_clear()

    with (
        patch.object(get_settings(), "sibyl_data_dir", str(data_dir)),
        patch(
            "app.services.chat.gather_chat_context",
            new_callable=AsyncMock,
            return_value=MINIMAL_REPO_CTX,
        ),
        patch("app.services.chat.is_llm_configured", return_value=False),
    ):
        return await process_chat_message(
            user,
            question,
            project,
            sibyl_enabled=sibyl_enabled,
        )


def _reply_covers(reply: str, keywords: list[str]) -> bool:
    lower = reply.lower()
    return any(kw.lower() in lower for kw in keywords)


async def run_simulation() -> int:
    from app.services import memory as memory_module

    print("=" * 72)
    print("KASSANDRA AI CTO - SIBYL MEMORY SIMULATION")
    print("=" * 72)
    print()
    print("Scenario: same GitHub repo evidence, same questions.")
    print("Only difference: Sibyl institutional memory ON vs OFF.")
    print()

    data_dir = _SERVER_ROOT / "data" / "sibyl_simulation"
    data_dir.mkdir(parents=True, exist_ok=True)

    memory_module._provider_cache.clear()
    _seed_sibyl_memory(data_dir)

    user = _make_user()
    project = _make_project()

    with_sibyl_pass = 0
    without_sibyl_pass = 0
    total = len(CTO_QUESTIONS)

    try:
        for i, (question, keywords, category) in enumerate(CTO_QUESTIONS, 1):
                print("-" * 72)
                print(f"Q{i} [{category}]: {question}")
                print("-" * 72)

                with_result = await _run_question(
                    user, project, question, sibyl_enabled=True, data_dir=data_dir
                )
                without_result = await _run_question(
                    user, project, question, sibyl_enabled=False, data_dir=data_dir
                )

                with_ok = _reply_covers(with_result["reply"], keywords)
                without_ok = _reply_covers(without_result["reply"], keywords)

                if with_ok:
                    with_sibyl_pass += 1
                if without_ok:
                    without_sibyl_pass += 1

                print()
                print(
                    f"  WITH Sibyl    | hits={with_result['memory_hits']:2d} | "
                    f"source={with_result['source']:<12} | "
                    f"CTO-capable: {'YES' if with_ok else 'NO'}"
                )
                snippet = with_result["reply"][:220]
                if len(with_result["reply"]) > 220:
                    snippet += "..."
                print(f"    > {snippet}")
                print()
                print(
                    f"  WITHOUT Sibyl | hits={without_result['memory_hits']:2d} | "
                    f"source={without_result['source']:<12} | "
                    f"CTO-capable: {'YES' if without_ok else 'NO'}"
                )
                snippet = without_result["reply"][:220]
                if len(without_result["reply"]) > 220:
                    snippet += "..."
                print(f"    > {snippet}")
                print()
    finally:
        memory_module._provider_cache.clear()

    print("=" * 72)
    print("VERDICT")
    print("=" * 72)
    print(
        f"  With Sibyl:    {with_sibyl_pass}/{total} "
        "questions answered with institutional knowledge"
    )
    print(
        f"  Without Sibyl: {without_sibyl_pass}/{total} "
        "questions answered with institutional knowledge"
    )
    print()

    if with_sibyl_pass > without_sibyl_pass:
        print("  [OK] Sibyl is load-bearing: the AI CTO role requires institutional memory.")
        print("       GitHub evidence alone cannot replace decisions, incidents, or policies.")
    else:
        print("  [WARN] Unexpected: Sibyl did not outperform disabled mode. Check memory seeding.")

    print()
    return 0 if with_sibyl_pass > without_sibyl_pass else 1


def main() -> None:
    raise SystemExit(asyncio.run(run_simulation()))


if __name__ == "__main__":
    main()
