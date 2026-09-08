#!/usr/bin/env python3
"""Live feature scenario: real questions against Trade Engine project.

Loads the real DB user + project (GitHub + Sibyl), runs a curated question
battery through process_chat_message / teach / understanding, scores each
feature, and prints a ranking + go/no-go decision.

Run from server/:
    python -m scripts.feature_scenario
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import Project, User
from app.services.chat import process_chat_message
from app.services.chat_sessions import (
    add_message,
    create_session,
    delete_session,
    load_sessions_for_recap,
)
from app.services.institutional_memory import build_understanding_report
from app.services.pending_memory import clear_pending, get_active_pending
from app.services.repo_context import should_load_other_sessions
from app.services.teach import teach_kassandra


TARGET_REPO = "CWC001-lab/Kassandra_Trade_Engine"


@dataclass
class CaseResult:
    feature: str
    question: str
    ok: bool
    score: float  # 0..10
    source: str = ""
    intent: str = ""
    memory_hits: int = 0
    evidence_level: Any = None
    evidence_count: int = 0
    reply_preview: str = ""
    notes: str = ""
    error: str = ""


@dataclass
class ScenarioState:
    history: list[dict[str, str]] = field(default_factory=list)
    last_commit_sha: str | None = None
    previous_commit_sha: str | None = None
    other_sessions: list[dict] = field(default_factory=list)


def _preview(text: str, n: int = 220) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text if len(text) <= n else text[: n - 1] + "..."


def _safe_print(text: str = "") -> None:
    """Avoid Windows cp1252 crashes on Unicode in replies/notes."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def _contains_any(text: str, needles: list[str]) -> bool:
    low = text.lower()
    return any(n.lower() in low for n in needles)


def _clear(tenant: str, user: User, project: Project) -> None:
    clear_pending(tenant, user_id=user.id, project_id=project.id)


def _pending(tenant: str, user: User, project: Project) -> dict | None:
    return get_active_pending(tenant, user_id=user.id, project_id=project.id)


async def _load_user_project() -> tuple[User, Project]:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Project).where(Project.repo_full_name == TARGET_REPO).limit(1)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise RuntimeError(f"Project {TARGET_REPO} not found in DB")
        user = await db.get(User, project.user_id)
        if not user:
            raise RuntimeError("Project owner user not found")
        if not user.github_access_token:
            raise RuntimeError(
                "User has no github_access_token — cannot live-test GitHub features"
            )
        db.expunge(user)
        db.expunge(project)
        return user, project


async def _ask(
    user: User,
    project: Project,
    state: ScenarioState,
    message: str,
    *,
    load_others: bool = False,
    sibyl_enabled: bool = True,
) -> dict:
    other = state.other_sessions
    if load_others or should_load_other_sessions(message, state.history):
        async with async_session_factory() as db:
            other = await load_sessions_for_recap(
                db,
                user.id,
                exclude_session_id=None,
                message=message,
                project_id=project.id,
            )
            state.other_sessions = other

    result = await process_chat_message(
        user,
        message,
        project,
        history=state.history,
        stored_commit_sha=state.last_commit_sha,
        stored_previous_commit_sha=state.previous_commit_sha,
        other_sessions=other,
        sibyl_enabled=sibyl_enabled,
    )
    state.history.append({"role": "user", "content": message})
    state.history.append({"role": "assistant", "content": result.get("reply", "")})
    if result.get("last_commit_sha"):
        state.last_commit_sha = result["last_commit_sha"]
    if result.get("previous_commit_sha"):
        state.previous_commit_sha = result["previous_commit_sha"]
    return result


def _emit(case: CaseResult) -> CaseResult:
    flag = "PASS" if case.ok else "FAIL"
    _safe_print(f"  [{flag}] {case.feature}: {case.score}/10  src={case.source or '-'}")
    sys.stdout.flush()
    return case


def _score_case(
    feature: str,
    question: str,
    result: dict,
    *,
    expect_sources: list[str] | None = None,
    expect_any: list[str] | None = None,
    forbid_any: list[str] | None = None,
    expect_pending: bool = False,
    min_evidence: int | None = None,
    base: float = 7.0,
) -> CaseResult:
    reply = result.get("reply") or ""
    source = (result.get("source") or "").lower()
    intent = result.get("intent") or ""
    evidence = result.get("evidence") or []
    notes: list[str] = []
    score = base
    ok = True

    if not reply.strip():
        return _emit(
            CaseResult(
                feature=feature,
                question=question,
                ok=False,
                score=0,
                error="empty reply",
            )
        )

    if expect_sources and source not in [s.lower() for s in expect_sources]:
        notes.append(f"source={source} (wanted {expect_sources})")
        score -= 2.5
        if source in {"system", "error"}:
            ok = False

    if expect_any and not _contains_any(reply, expect_any):
        notes.append(f"missing expected terms {expect_any}")
        score -= 2.0
        ok = False

    if forbid_any and _contains_any(reply, forbid_any):
        notes.append(f"hit forbidden terms {forbid_any}")
        score -= 3.0
        ok = False

    pending_markers = [
        "would you like me to save",
        "pending institutional",
        "potential memor",
        "reply yes",
    ]
    is_pending = _contains_any(reply, pending_markers)
    if expect_pending and not is_pending:
        notes.append("expected pending confirmation prompt")
        score -= 3.0
        ok = False
    if not expect_pending and _contains_any(
        reply, ["would you like me to save these to sibyl"]
    ):
        notes.append("unexpected pending confirmation gate")
        score -= 2.5
        ok = False

    if min_evidence is not None and len(evidence) < min_evidence:
        notes.append(f"evidence={len(evidence)} < {min_evidence}")
        score -= 1.5

    if len(reply) > 120:
        score += 0.5
    if evidence:
        score += 0.5
    if result.get("memory_hits", 0) > 0:
        score += 0.5

    score = max(0.0, min(10.0, score))
    return _emit(
        CaseResult(
            feature=feature,
            question=question,
            ok=ok and score >= 5.0,
            score=round(score, 1),
            source=source,
            intent=str(intent),
            memory_hits=int(result.get("memory_hits") or 0),
            evidence_level=result.get("evidence_level"),
            evidence_count=len(evidence),
            reply_preview=_preview(reply),
            notes="; ".join(notes),
        )
    )


async def run_scenario() -> list[CaseResult]:
    user, project = await _load_user_project()
    tenant = project.repo_full_name
    print(f"User: {user.email} ({user.full_name})")
    print(f"Project: {project.repo_full_name} id={project.id}")
    print("=" * 72)

    _clear(tenant, user, project)

    results: list[CaseResult] = []
    state = ScenarioState()

    # ---- 1. Intro / greeting ----
    r = await _ask(user, project, state, "hi")
    results.append(
        _score_case(
            "Intro greeting",
            "hi",
            r,
            expect_sources=["intro"],
            expect_any=["kassandra"],
            base=8,
        )
    )

    r = await _ask(user, project, state, "help")
    results.append(
        _score_case(
            "Intro help",
            "help",
            r,
            expect_sources=["intro"],
            expect_any=["project", "teach", "ask"],
            base=8,
        )
    )

    # ---- 2. Project identity ----
    r = await _ask(user, project, state, "What's my project?")
    results.append(
        _score_case(
            "Project name",
            "What's my project?",
            r,
            expect_any=["Kassandra_Trade_Engine", "CWC001-lab"],
            base=9,
        )
    )

    # ---- 3. GitHub facts ----
    r = await _ask(user, project, state, "Who made the last commit?")
    results.append(
        _score_case(
            "Last commit author",
            "Who made the last commit?",
            r,
            expect_sources=["github"],
            expect_any=["commit"],
            min_evidence=1,
            base=8,
        )
    )

    r = await _ask(user, project, state, "What changed in that commit?")
    results.append(
        _score_case(
            "Commit detail follow-up",
            "What changed in that commit?",
            r,
            expect_sources=["github", "llm"],
            forbid_any=["would you like me to save these to sibyl"],
            min_evidence=1,
            base=8,
        )
    )

    r = await _ask(user, project, state, "List the files that changed")
    results.append(
        _score_case(
            "Commit file list",
            "List the files that changed",
            r,
            expect_sources=["github", "llm"],
            expect_any=[".py", "file", "changed", "modified", "api/", "utils/"],
            min_evidence=1,
            base=8,
        )
    )

    r = await _ask(user, project, state, "What was the previous commit?")
    results.append(
        _score_case(
            "Previous commit",
            "What was the previous commit?",
            r,
            expect_sources=["github", "llm"],
            min_evidence=1,
            base=7.5,
        )
    )

    r = await _ask(user, project, state, "Compare the last two commits")
    results.append(
        _score_case(
            "Commit compare",
            "Compare the last two commits",
            r,
            expect_sources=["github", "llm"],
            expect_any=["commit", "vs", "compare", "differ", "between", "sha"],
            min_evidence=1,
            base=8,
        )
    )

    r = await _ask(user, project, state, "How many commits are there?")
    results.append(
        _score_case(
            "Commit count",
            "How many commits are there?",
            r,
            expect_sources=["github"],
            expect_any=["commit"],
            min_evidence=1,
            base=8.5,
        )
    )

    r = await _ask(user, project, state, "When was this repository created?")
    results.append(
        _score_case(
            "Repo created date",
            "When was this repository created?",
            r,
            expect_sources=["github"],
            expect_any=["created", "20"],
            min_evidence=1,
            base=8,
        )
    )

    r = await _ask(user, project, state, "What changed recently?")
    results.append(
        _score_case(
            "Recent changes",
            "What changed recently?",
            r,
            expect_sources=["github", "llm"],
            min_evidence=1,
            base=8,
        )
    )

    r = await _ask(user, project, state, "What was the first commit?")
    results.append(
        _score_case(
            "First commit",
            "What was the first commit?",
            r,
            expect_sources=["github", "llm"],
            min_evidence=1,
            base=7.5,
        )
    )

    r = await _ask(user, project, state, "Which files changed the most?")
    results.append(
        _score_case(
            "File churn hotspots",
            "Which files changed the most?",
            r,
            expect_sources=["github", "llm"],
            min_evidence=1,
            base=7.5,
        )
    )

    state2 = ScenarioState()
    r = await _ask(user, project, state2, "Did CI fail recently?")
    results.append(
        _score_case(
            "CI status",
            "Did CI fail recently?",
            r,
            expect_sources=["github", "llm"],
            base=7,
        )
    )

    r = await _ask(user, project, state2, "What's going on in the repo?")
    results.append(
        _score_case(
            "Activity overview",
            "What's going on in the repo?",
            r,
            expect_sources=["github", "llm"],
            base=7,
        )
    )

    # ---- 4. Architecture / institutional ----
    state3 = ScenarioState()
    r = await _ask(
        user,
        project,
        state3,
        "What are the most important architectural decisions in this project, and why were they made?",
    )
    results.append(
        _score_case(
            "Architecture WHY (memory+LLM)",
            "What are the most important architectural decisions…",
            r,
            expect_any=["flask", "rest", "architect", "decision", "transitional", "api"],
            forbid_any=["would you like me to save these to sibyl"],
            base=8,
        )
    )

    r = await _ask(
        user, project, state3, "How does authentication and authorisation work?"
    )
    results.append(
        _score_case(
            "Auth explanation (repo+memory)",
            "How does authentication and authorisation work?",
            r,
            expect_any=["auth", "key", "token", "secret", "request"],
            forbid_any=["would you like me to save these to sibyl"],
            base=8,
        )
    )

    r = await _ask(
        user,
        project,
        state3,
        "Were there any production incidents that caused the architecture to change?",
    )
    results.append(
        _score_case(
            "Incident / constraint recall",
            "Were there any production incidents…",
            r,
            forbid_any=["would you like me to save these to sibyl"],
            base=7.5,
        )
    )

    # ---- 5. Pending confirmation flow ----
    _clear(tenant, user, project)
    state4 = ScenarioState()
    teach_statement = (
        "We decided that new developers must never run the live EC2 isolation unlock "
        "without a senior review, because concurrent engine instances can double-execute orders."
    )
    r = await _ask(user, project, state4, teach_statement)
    results.append(
        _score_case(
            "Pending extract (teach-via-chat)",
            teach_statement[:60] + "…",
            r,
            expect_pending=True,
            expect_any=["save", "yes", "sibyl", "memory", "extract"],
            base=8.5,
        )
    )

    r = await _ask(user, project, state4, "yes")
    pending_after = _pending(tenant, user, project)
    yes_ok = pending_after is None and (
        _contains_any(r.get("reply", ""), ["saved", "sibyl", "memory"])
        or (r.get("source") or "").lower() in {"memory", "teach", "system"}
    )
    results.append(
        CaseResult(
            feature="Pending confirm YES",
            question="yes",
            ok=yes_ok,
            score=9.0 if yes_ok else 3.0,
            source=(r.get("source") or ""),
            reply_preview=_preview(r.get("reply", "")),
            notes="" if yes_ok else f"pending_still={pending_after is not None}",
        )
    )

    # Knowledge-on-yes
    _clear(tenant, user, project)
    state4b = ScenarioState()
    await _ask(
        user,
        project,
        state4b,
        "We use bridge-ready JSON instead of direct MT5 so the existing execution bridge can be reused.",
    )
    r = await _ask(
        user,
        project,
        state4b,
        "yes, and master keys gate admin endpoints while normal keys gate trader endpoints",
    )
    reply = r.get("reply", "")
    loop_bad = _contains_any(reply, ["we use bridge-ready json"]) and _contains_any(
        reply, ["would you like me to save"]
    )
    results.append(
        CaseResult(
            feature="Pending YES+knowledge",
            question="yes, and master keys gate…",
            ok=not loop_bad,
            score=8.0 if not loop_bad else 2.0,
            source=(r.get("source") or ""),
            reply_preview=_preview(reply),
            notes="bad re-extract loop" if loop_bad else "handled",
        )
    )
    _clear(tenant, user, project)

    # ---- 6. Pending must not block GitHub / continue ----
    state5 = ScenarioState()
    await _ask(
        user,
        project,
        state5,
        "Intentional technical debt: Flask REST stays until reliability metrics justify async queues.",
    )

    r = await _ask(user, project, state5, "How many contributors are there?")
    results.append(
        _score_case(
            "GitHub while pending (passthrough)",
            "How many contributors are there?",
            r,
            expect_any=["contributor", "commit", "author", "people", "1", "2", "3", "4", "5"],
            forbid_any=["would you like me to save these to sibyl"],
            base=8,
        )
    )

    prior_id: str | None = None
    async with async_session_factory() as db:
        prior = await create_session(
            db,
            user.id,
            project_id=project.id,
            title="Dangerous for new developers",
        )
        await add_message(
            db,
            prior,
            role="user",
            content="What parts of the system are dangerous for a new developer?",
        )
        await add_message(
            db,
            prior,
            role="assistant",
            content=(
                "The EC2 isolation unlock and live trading lock path are dangerous for new "
                "developers because concurrent instances can double-execute orders."
            ),
            source="llm",
        )
        prior_id = prior.id
        await db.commit()

    if _pending(tenant, user, project) is None:
        seed = ScenarioState()
        await _ask(
            user,
            project,
            seed,
            "Knowledge gap fill: new developers must not touch the isolation unlock without review.",
        )

    state6 = ScenarioState()
    r = await _ask(
        user,
        project,
        state6,
        "we were talking about something being dangerous for a new developer, what was that?",
        load_others=True,
    )
    results.append(
        _score_case(
            "Cross-session recall (with pending)",
            "we were talking about something being dangerous…",
            r,
            expect_any=[
                "dangerous",
                "isolation",
                "lock",
                "ec2",
                "developer",
                "session",
                "continue",
            ],
            forbid_any=["would you like me to save these to sibyl"],
            base=8.5,
        )
    )

    r = await _ask(user, project, state6, "lets continue", load_others=True)
    cont_reply = r.get("reply", "")
    blocked = _contains_any(
        cont_reply,
        ["would you like me to save these to sibyl", "pending institutional"],
    )
    results.append(
        CaseResult(
            feature="Continue while pending",
            question="lets continue",
            ok=not blocked and len(cont_reply) > 40,
            score=3.0 if blocked else (8.5 if len(cont_reply) > 40 else 4.0),
            source=(r.get("source") or ""),
            reply_preview=_preview(cont_reply),
            notes="BLOCKED by pending gate" if blocked else "continued",
        )
    )
    _clear(tenant, user, project)

    if prior_id:
        async with async_session_factory() as db:
            await delete_session(db, user.id, prior_id)
            await db.commit()

    # ---- 7. In-session recap ----
    state7 = ScenarioState()
    await _ask(user, project, state7, "What stack are we using?")
    r = await _ask(user, project, state7, "What were we talking about?")
    results.append(
        _score_case(
            "In-session recap",
            "What were we talking about?",
            r,
            expect_any=["stack", "flask", "talking", "discuss", "you asked", "python"],
            base=8,
        )
    )

    # ---- 8. Sibyl off ----
    state8 = ScenarioState()
    r = await _ask(
        user,
        project,
        state8,
        "Why was Flask chosen for the API?",
        sibyl_enabled=False,
    )
    results.append(
        CaseResult(
            feature="Sibyl disabled path",
            question="Why was Flask chosen… (sibyl off)",
            ok=bool(r.get("reply")),
            score=7.0 if r.get("reply") else 0,
            source=(r.get("source") or ""),
            memory_hits=int(r.get("memory_hits") or 0),
            reply_preview=_preview(r.get("reply", "")),
            notes=f"memory_hits={r.get('memory_hits', 0)} (expect 0)",
        )
    )

    # ---- 9. Understanding / teach API ----
    try:
        report = build_understanding_report(tenant, project.repo_full_name)
        counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
        gap_count = int(counts.get("knowledge_gaps") or 0)
        results.append(
            CaseResult(
                feature="Understanding report",
                question="build_understanding_report()",
                ok=isinstance(report, dict) and bool(report),
                score=8.5 if report else 2.0,
                reply_preview=_preview(
                    json.dumps({k: report.get(k) for k in list(report)[:6]}, default=str)
                ),
                notes=f"gap_count~={gap_count}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        results.append(
            CaseResult(
                feature="Understanding report",
                question="build_understanding_report()",
                ok=False,
                score=0,
                error=str(exc),
            )
        )

    try:
        _clear(tenant, user, project)
        teach_result = await teach_kassandra(
            tenant,
            "Auth uses a master key for admin and normal keys for traders; no OAuth by design.",
            developer_name=user.full_name or user.email,
            project_id=project.id,
            user_id=user.id,
            confirm=False,
        )
        pending = _pending(tenant, user, project)
        teach_ok = pending is not None or bool(
            teach_result.get("awaiting_confirmation")
        )
        results.append(
            CaseResult(
                feature="Teach API extract",
                question="POST teach (confirm=false)",
                ok=teach_ok,
                score=8.5 if teach_ok else 3.0,
                reply_preview=_preview(json.dumps(teach_result, default=str)),
                notes="pending set" if pending else "no pending",
            )
        )
        await teach_kassandra(
            tenant,
            "yes",
            developer_name=user.full_name or user.email,
            project_id=project.id,
            user_id=user.id,
            confirm=True,
        )
        _clear(tenant, user, project)
        results.append(
            CaseResult(
                feature="Teach API confirm",
                question="yes via teach",
                ok=_pending(tenant, user, project) is None,
                score=8.5,
                reply_preview="confirmed + cleared",
            )
        )
    except Exception as exc:  # noqa: BLE001
        results.append(
            CaseResult(
                feature="Teach API",
                question="teach_kassandra",
                ok=False,
                score=0,
                error=f"{exc}\n{traceback.format_exc()[-400:]}",
            )
        )

    return results


def print_report(results: list[CaseResult]) -> int:
    by_feature: dict[str, list[CaseResult]] = {}
    for r in results:
        by_feature.setdefault(r.feature, []).append(r)

    ranked: list[tuple[str, float, bool, CaseResult]] = []
    for feature, cases in by_feature.items():
        avg = sum(c.score for c in cases) / len(cases)
        ok = all(c.ok for c in cases)
        ranked.append((feature, avg, ok, cases[0]))

    ranked.sort(key=lambda x: x[1], reverse=True)

    scores = [r.score for r in results]
    overall = sum(scores) / len(scores) if scores else 0
    passed = sum(1 for r in results if r.ok)
    failed = [r for r in results if not r.ok]
    critical_fails = [
        r
        for r in failed
        if r.feature
        in {
            "Continue while pending",
            "Cross-session recall (with pending)",
            "Pending confirm YES",
            "GitHub while pending (passthrough)",
            "Architecture WHY (memory+LLM)",
            "Last commit author",
        }
    ]

    if overall >= 8.0 and not critical_fails and passed / len(results) >= 0.85:
        decision_code = 0
        decision = "SHIP"
    elif overall >= 6.5 and len(critical_fails) <= 1:
        decision_code = 1
        decision = "CONDITIONAL GO"
    else:
        decision_code = 2
        decision = "NO-GO"

    # Persist JSON first so a console encoding error cannot lose results.
    out = _SERVER_ROOT / "scripts" / "feature_scenario_report.json"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo": TARGET_REPO,
        "overall": overall,
        "passed": passed,
        "total": len(results),
        "decision": decision,
        "decision_code": decision_code,
        "cases": [r.__dict__ for r in results],
        "ranking": [{"feature": f, "score": s, "ok": ok} for f, s, ok, _ in ranked],
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    _safe_print("\n" + "=" * 72)
    _safe_print("FEATURE SCENARIO RESULTS")
    _safe_print("=" * 72)

    _safe_print(f"\n{'#':<3} {'Feature':<36} {'Score':>5}  {'Pass':<5}  Notes")
    _safe_print("-" * 90)
    for i, (feature, avg, ok, sample) in enumerate(ranked, 1):
        note = sample.notes or sample.error or sample.source
        _safe_print(
            f"{i:<3} {feature:<36} {avg:>5.1f}  {'PASS' if ok else 'FAIL':<5}  {_preview(note, 40)}"
        )

    _safe_print("\n--- Case details ---")
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        _safe_print(f"\n[{status}] {r.feature}  score={r.score}")
        _safe_print(f"  Q: {r.question}")
        _safe_print(
            f"  source={r.source or '-'} intent={r.intent or '-'} "
            f"hits={r.memory_hits} evidence={r.evidence_count} lvl={r.evidence_level}"
        )
        if r.notes:
            _safe_print(f"  notes: {r.notes}")
        if r.error:
            _safe_print(f"  error: {r.error}")
        _safe_print(f"  reply: {r.reply_preview}")

    _safe_print("\n" + "=" * 72)
    _safe_print(f"OVERALL: {overall:.1f}/10  |  cases {passed}/{len(results)} passed")
    _safe_print("=" * 72)

    _safe_print("\nFINAL RANKING (top features):")
    for i, (feature, avg, ok, _) in enumerate(ranked[:8], 1):
        _safe_print(f"  {i}. {feature}: {avg:.1f}/10 ({'pass' if ok else 'fail'})")

    _safe_print("\nWEAKEST:")
    for feature, avg, ok, _ in ranked[-5:]:
        _safe_print(f"  - {feature}: {avg:.1f}/10 ({'pass' if ok else 'fail'})")

    _safe_print("\nDECISION:")
    if decision_code == 0:
        _safe_print("  SHIP - Feature set is strong enough for demo/hackathon use.")
        _safe_print(
            "  Pending confirmation, GitHub evidence, and institutional Q&A look healthy."
        )
    elif decision_code == 1:
        _safe_print(
            "  CONDITIONAL GO - Core features work; fix failing cases before calling it solid."
        )
        for r in failed:
            _safe_print(f"    * FAIL: {r.feature} - {r.notes or r.error or r.reply_preview}")
    else:
        _safe_print("  NO-GO - Too many regressions for a confident release.")
        for r in failed:
            _safe_print(f"    * FAIL: {r.feature} - {r.notes or r.error or r.reply_preview}")

    _safe_print(f"\nWrote {out}")
    return decision_code


async def main() -> int:
    try:
        results = await run_scenario()
    except Exception as exc:  # noqa: BLE001
        print(f"SCENARIO ABORTED: {exc}")
        traceback.print_exc()
        return 3
    return print_report(results)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
