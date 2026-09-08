"""Chat orchestration — intro checker, memory context, repo evidence, LLM."""

from __future__ import annotations

import logging
import re

from app.services.commit_compare import answer_multi_commit_compare_without_llm
from app.services.github import analyze_file_churn, get_repo
from app.services.intro import check_intro_message, get_welcome_message
from app.services.llm import LLMError, chat_completion, is_llm_configured
from app.services.memory import get_memory_provider
from app.services.repo_context import (
    _is_other_session_follow_up,
    answer_activity_overview,
    answer_ci_status,
    answer_commit_changes_without_llm,
    answer_commit_compare_without_llm,
    answer_commit_count,
    answer_commit_file_list,
    answer_contributor_count,
    answer_commit_endpoints_without_llm,
    answer_conversation_recap,
    answer_cross_session_recap,
    answer_cross_session_continuation,
    answer_deployments,
    answer_file_churn,
    answer_file_history,
    answer_first_commit_without_llm,
    answer_parent_commit,
    answer_last_commit_author,
    answer_previous_commit,
    answer_recent_changes,
    answer_releases,
    answer_repo_created,
    extract_commit_sha,
    fetch_commit_context,
    fetch_commit_endpoints_context,
    fetch_first_commit_context,
    fetch_compare_context,
    fetch_file_history_context,
    fetch_multi_compare_context,
    fetch_recent_commit_shas,
    format_context_for_llm,
    gather_chat_context,
    gather_repo_stats,
    get_latest_commit_sha,
    get_previous_commit_sha,
    implies_other_session,
    is_continuation_request,
    is_explicit_recap_request,
    is_activity_overview_question,
    is_ci_question,
    is_commit_change_question,
    is_commit_compare_question,
    is_commit_count_question,
    is_commit_endpoints_question,
    is_commit_file_list_question,
    is_contributor_question,
    is_conversation_recap_question,
    is_cross_session_question,
    is_deployment_question,
    is_file_churn_question,
    is_file_history_question,
    is_first_commit_question,
    is_last_commit_author_question,
    is_parent_commit_question,
    is_previous_commit_question,
    is_project_name_question,
    is_recent_changes_question,
    is_release_question,
    is_repo_created_question,
    mentions_commit_sha,
    needs_session_recap,
    parse_recent_commit_count,
    parse_time_hint,
    prefers_breakdown_summary,
    should_use_other_sessions,
    resolve_commit_targets,
    should_fetch_commit_detail,
)
from app.services.evidence_integrity import (
    EvidenceLevel,
    build_commit_context_annotations,
    build_self_correction_preamble,
    collect_known_shas,
    find_memory_git_conflicts,
    find_prior_unavailability_claim,
    find_stats_discrepancy,
    format_evidence_escalation_note,
    infer_evidence_level,
    sanitize_llm_reply,
    validate_canonical_sha,
)
from app.services.evidence import (
    activity_overview_evidence,
    build_question_evidence,
    ci_evidence,
    deployment_evidence,
    file_churn_evidence,
    last_commit_author_evidence,
    merge_evidence,
    normalize_evidence,
    previous_commit_evidence,
    recent_changes_evidence,
    release_evidence,
    repo_created_evidence,
    repo_stats_evidence_refs,
    session_evidence,
    sibyl_memory_evidence,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Kassandra, an AI CTO with institutional engineering memory.

CORE RULE: EVIDENCE FIRST → MEMORY SECOND → REASONING THIRD

Repository data for this question has been pre-fetched from GitHub and is provided below.
Answer from that evidence and project memory. Never mention internal tools, repo_browser,
or say things like "let me fetch", "we need to call", or "not sure of exact tool".

Never say "I don't have that information" or "the evidence you shared" when commit files,
diffs, or metadata appear in the context below — use that data directly.

Never guess. Only state facts from the provided evidence.
Never synthesize identifiers (commit SHAs, branch names, file paths, PR/issue numbers,
URLs, versions). If only a short SHA is known, use the short SHA. If a full SHA is required,
it must come from GitHub evidence — never complete or guess the remaining characters.
When evidence depth increases (e.g. metadata → full file manifest), explain that escalation
briefly so the user knows deeper GitHub retrieval occurred.
When a prior answer was wrong or incomplete, correct it explicitly — correctness matters
more than conversational consistency.
When the purpose of a change cannot be determined from the diff, say so explicitly.
Do NOT use words like "likely" or "probably" unless you label them as inference.

PROVENANCE AND CONFIDENCE (label internally; use plain language in replies):
- VERIFIED facts come directly from GitHub (SHA, dates, files, diffs, parents).
- DERIVED facts are calculated from GitHub data (e.g. file counts, set comparisons).
- OBSERVED institutional facts come from repository analysis stored in Sibyl.
- INFERRED statements are engineering interpretation — always label them; never promote to fact.
- CONFIRMED / RECORDED context comes from Sibyl institutional memory (developer-taught or prior) — use for WHY.
- UNKNOWN means the authoritative evidence was not retrieved or does not contain the answer.

For important architecture or institutional questions, organize your reasoning as:
OBSERVED (what repo/GitHub proves) → CONFIRMED (what the developer explicitly taught) →
INFERRED (your conclusions, labeled) → UNKNOWN (what cannot be established).
Then synthesize a plain-language answer. Do not turn guesses into facts.

ABSENCE OF EVIDENCE IS NOT EVIDENCE OF ABSENCE:
- If you find no repository or Sibyl evidence of an incident/outage/decision, say you found
  no evidence in available records — do NOT claim the event never happened.
- Prefer: "I found no repository or institutional-memory evidence of X. That does not prove
  X never occurred outside these records."

INTENT vs IMPLEMENTATION:
- Developer-confirmed INTENT is what the system is designed/meant to do.
- IMPLEMENTATION is what the current code actually supports.
- Never equate "developer said we support multiple user keys" with "the code fully implements
  key generation, revocation, rotation, and user management" unless those are OBSERVED.
- When they diverge, report CURRENT IMPLEMENTATION separately from INTENDED DESIGN.

SECURITY CLAIMS MUST BE EVIDENCE-STRICT:
- Only state how auth works (headers, token format, hashing, revocation, roles, expiry) when
  the repository or a CONFIRMED memory explicitly establishes it. Otherwise say UNKNOWN.

ARCHITECTURE STATE:
- Distinguish CURRENT, HISTORICAL, PLANNED, and DEPRECATED architecture.
- Do not present historical design as current capability.
- Intentional technical debt (tagged INTENTIONAL_TECH_DEBT) is a known compromise, not a bug.

CONTRADICTIONS:
- If code OBSERVED behavior conflicts with CONFIRMED developer intent, surface both explicitly.
  Do not silently choose one.

Never confuse "the system does X" (observable) with "the team decided X because Y" (institutional).
If Sibyl memory includes knowledge gaps, prefer asking targeted questions over inventing rationale.

Do not confuse "I have not retrieved this yet" with "it does not exist in the repository."
If repository facts are required, use the pre-fetched GitHub evidence below — do not rely on
conversation memory alone when authoritative data is provided.

When a DISCREPANCY NOTE or EVIDENCE ESCALATION note appears in the context, acknowledge it
explicitly in your reply when relevant. Prefer authoritative GitHub data over earlier
conversational claims. Correct prior errors if the user asks or if the conflict is material.

Contributor precision: distinguish repository-wide contributors (GitHub contributors API)
from authors visible on a specific branch or in retrieved commit history. Do not equate
"only contributor on this branch's recent commits" with "only contributor in the repository."

Repository statistics (commit counts, contributor lists) are included when available.
Use those exact numbers — do not say data is unavailable if it appears in the evidence.

Repository activity data is pre-fetched from GitHub and may include:
- GitHub Actions workflow runs and build logs
- Deployments and deployment statuses
- Releases, tags, and branches
- Repository event feed (pushes, PRs, issues, releases)

Use this activity data when answering about CI/CD, deployments, builds, releases,
or what is happening in the repository. Quote actual log excerpts when provided.

CHAT SESSION vs PROJECT MEMORY (Sibyl):
- "Recent conversation" and message history = this chat session only
- "Project memory" = Sibyl Memory — persistent institutional engineering memory
  (decisions, incidents, architecture rationale) stored via the Sibyl layer
- Sibyl memory is separate from GitHub repository evidence; never conflate them
- When Sibyl memory is provided below, use it only for engineering context and rationale
When asked what you discussed previously in THIS chat, use the session history only.
If "Other chat sessions" evidence is provided below, use that for cross-session recap.
Do not confuse the welcome message with prior user questions.

When answering about a SPECIFIC COMMIT:
- Focus on THAT commit only — not a broad list of recent commits
- Distinguish commit message (intent) from actual diff (what changed)
- Use the authoritative file count from the commit detail (files changed count)
- If a "Specific commit detail" section is provided, use its file list and diff
- If a file list is provided without a diff, still enumerate the files changed
- Only say diff is unavailable if neither files nor diff are in the evidence

When comparing two commits:
- Use the FILE SUMMARY counts exactly as provided — do not recalculate
- TOTAL CHANGED and UNIQUE TO COMMIT are different: only_A excludes shared files
- Never write "only in A (N total)" where N is the total changed count for A
- The math must hold: total_A = only_A + shared, total_B = only_B + shared
- Label conclusions as VERIFIED (from GitHub file list or diff), INFERENCE, or UNKNOWN
- Do not invent file names or change purposes not shown in the diff
- For shared files, describe each commit's changes separately when diffs are available
- If a diff is missing, say the file changed but the purpose cannot be determined

When comparing three or more commits:
- Commit data is retrieved fresh from GitHub — never say you only have previously supplied data
- Use TWO orderings: repository order (newest → oldest) for recent history; chronological order (oldest → newest) for engineering evolution
- Always analyze evolution in chronological order (oldest → newest)
- Refer to commits by SHA and position (oldest / middle / newest), never ambiguous "Commit 1/2/3"
- A later commit may revisit or refine a file; never say an older commit revisits a newer one
- Use THREE-WAY FILE MEMBERSHIP and FILE EVOLUTION sections exactly as provided
- Label trajectory conclusions as INFERENCE; file membership is VERIFIED from GitHub
- Sibyl memory provides engineering rationale — keep it separate from GitHub evidence

Never say "I can only work with the data that has been supplied" when the repository
is connected — missing commit data should be retrieved from GitHub first.

RESPONSE FORMAT:
- Plain conversational text like ChatGPT
- Short paragraphs, line breaks between sections
- Use "•" for bullet lists when helpful
- NO markdown tables, NO **bold**, NO # headers, NO backticks, NO JSON
- Never expose your reasoning process

Current project: {repo_name}
"""

_TOOL_LEAK_PATTERNS = [
    re.compile(r"repo_browser[^\n]*", re.IGNORECASE),
    re.compile(r"We need to (call|get|use)[^\n]*", re.IGNORECASE),
    re.compile(r"Let's try[^\n]*", re.IGNORECASE),
    re.compile(r"Not sure of exact tool[^\n]*", re.IGNORECASE),
    re.compile(r'\{\s*"tool"\s*:', re.IGNORECASE),
    re.compile(r"I could list files and view[^\n]*but the provided tooling[^\n]*", re.IGNORECASE),
]


def _clean_response(text: str) -> str:
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("|") and "|" in stripped[1:]:
            continue
        if stripped.startswith("#"):
            line = stripped.lstrip("#").strip()
        if any(p.search(line) for p in _TOOL_LEAK_PATTERNS):
            continue
        if stripped.startswith("{") and '"tool"' in stripped:
            continue
        lines.append(line)
    result = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", result)


_SIBYL_DISABLED_BLOCK = (
    "Sibyl memory is OFF. No institutional engineering memory is available — "
    "you cannot answer from past decisions, incidents, or architecture rationale."
)


def _gap_count_for_project(project: Project | None) -> int:
    if not project:
        return 0
    try:
        from app.services.institutional_memory import build_understanding_report

        report = build_understanding_report(project.repo_full_name, project.repo_full_name)
        return int((report.get("counts") or {}).get("knowledge_gaps") or 0)
    except Exception:  # noqa: BLE001
        return 0


def _format_memory_context(hits: list, *, sibyl_enabled: bool = True) -> str:
    if not sibyl_enabled:
        return _SIBYL_DISABLED_BLOCK
    if not hits:
        return "No relevant project memory entries found."
    from app.services.institutional_memory import format_memory_line

    lines: list[str] = []
    for hit in hits[:12]:
        if not isinstance(hit, dict):
            lines.append(f"• {hit}")
            continue
        # Prefer structured institutional memories with explicit provenance
        if hit.get("confidence") and (hit.get("title") or hit.get("decision")):
            lines.append(f"• {format_memory_line(hit)}")
            continue
        body = hit.get("body")
        if isinstance(body, dict) and body.get("confidence"):
            lines.append(f"• {format_memory_line(body)}")
            continue
        content = hit.get("content") or hit.get("text") or hit.get("summary") or str(hit)
        conf = hit.get("confidence")
        prefix = f"[{str(conf).upper()}] " if conf else ""
        lines.append(f"• {prefix}{content}")
    return (
        "Institutional memory from Sibyl (OBSERVED = repo evidence, "
        "INFERRED = system inference, CONFIRMED = developer):\n"
        + "\n".join(lines)
    )


def _should_search_memory(text: str) -> bool:
    """Sibyl is for engineering memory — not chat recap or pure GitHub metadata."""
    if is_conversation_recap_question(text):
        return False
    if is_cross_session_question(text):
        return False
    if is_repo_created_question(text):
        return False
    if is_file_churn_question(text):
        return False
    if is_file_history_question(text):
        return False
    if is_commit_count_question(text):
        return False
    if is_commit_endpoints_question(text):
        return False
    if is_first_commit_question(text):
        return False
    if is_contributor_question(text):
        return False
    return True


def _search_memory(tenant_id: str, query: str) -> list:
    try:
        provider = get_memory_provider(tenant_id)
        results = provider.search(query)
        return list(results) if results else []
    except Exception as exc:  # noqa: BLE001
        logger.warning("Memory search failed for %s: %s", tenant_id, exc)
        return []


def _prepend_preamble(reply: str, preamble: str | None) -> str:
    if not preamble or preamble in reply:
        return reply
    return f"{preamble}\n\n{reply}"


def _finalize_llm_reply(
    reply: str,
    *,
    history: list[dict[str, str]] | None = None,
    detail: dict | None = None,
    extra_contexts: list | None = None,
) -> str:
    cleaned = _clean_response(reply)
    known_shas = collect_known_shas(detail, *(extra_contexts or []))
    return sanitize_llm_reply(cleaned, known_shas=known_shas, history=history)


def _memory_conflict_block(memory_hits: list, **github_facts) -> str:
    conflicts = find_memory_git_conflicts(memory_hits, **github_facts)
    if not conflicts:
        return ""
    return "\n\n".join(conflicts)


def _build_llm_messages(
    repo_label: str,
    context_parts: list[str],
    history: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(repo_name=repo_label)
            + "\n\n"
            + "\n\n".join(context_parts),
        },
    ]
    for msg in history[-10:]:
        if msg["role"] in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


async def process_chat_message(
    user: User,
    message: str,
    project: Project | None,
    *,
    history: list[dict[str, str]] | None = None,
    stored_commit_sha: str | None = None,
    stored_previous_commit_sha: str | None = None,
    other_sessions: list[dict] | None = None,
    sibyl_enabled: bool = True,
) -> dict:
    """Process a user chat message and return the assistant reply."""
    text = message.strip()
    history = history or []
    last_commit_sha: str | None = stored_commit_sha
    previous_commit_sha: str | None = stored_previous_commit_sha

    if not text:
        return _result("Please enter a message.", "system", project, [], [])

    # Session recap must run before intro — "hi, continue where we left off" is not a greeting
    if needs_session_recap(text):
        if should_use_other_sessions(text, history, other_sessions):
            if (
                prefers_breakdown_summary(text)
                or is_continuation_request(text)
                or _is_other_session_follow_up(text, history)
            ):
                reply = _clean_response(
                    answer_cross_session_continuation(
                        other_sessions or [],
                        repo_name=project.repo_full_name if project else None,
                    )
                )
                evidence = [
                    session_evidence("Prior session context (not repository evidence)")
                ]
            else:
                time_hint = parse_time_hint(text)
                time_label = (
                    time_hint.strftime("%I:%M %p").lstrip("0") if time_hint else None
                )
                reply = _clean_response(
                    answer_cross_session_recap(
                        history,
                        other_sessions or [],
                        time_hint_label=time_label,
                    )
                )
                evidence = [session_evidence("Cross-session history")]
                for sess in (other_sessions or [])[:2]:
                    evidence.append(
                        session_evidence(f"Chat: {sess.get('title', 'Untitled')}")
                    )
            return _result(reply, "session", project, [], evidence, sibyl_enabled=sibyl_enabled, is_session=True)

        reply = _clean_response(answer_conversation_recap(history))
        return _result(reply, "session", project, [], [session_evidence("Chat session history")], sibyl_enabled=sibyl_enabled, is_session=True)

    intro = check_intro_message(
        text,
        user_name=user.full_name or user.github_username,
        repo_full_name=project.repo_full_name if project else None,
        gap_count=_gap_count_for_project(project),
    )
    if intro:
        return _result(
            _clean_response(intro.response),
            "intro",
            project,
            [],
            [],
            intent=intro.intent.value,
        )

    tenant_id = project.repo_full_name if project else "default"
    repo_label = project.repo_full_name if project else "no project selected"

    # Pending confirmation FIRST — "yes"/"no" are control actions, never extraction input
    if project and sibyl_enabled:
        from app.services.teach import process_teach_control_or_extract

        teach_flow = await process_teach_control_or_extract(
            tenant_id,
            text,
            user_id=user.id,
            project_id=project.id,
            developer_name=user.full_name,
        )
        if teach_flow and not teach_flow.get("passthrough_chat"):
            reply = teach_flow.get("reply") or teach_flow.get("reason") or ""
            intent = teach_flow.get("intent")
            if intent in {"confirm_all", "select"} and teach_flow.get("ok"):
                stored = teach_flow.get("stored") or teach_flow.get("verified") or []
                return _result(
                    _clean_response(reply),
                    "memory",
                    project,
                    stored if isinstance(stored, list) else [],
                    [],
                    intent="teach_confirm",
                )
            if intent == "reject":
                return _result(
                    _clean_response(reply or "Discarded pending memories."),
                    "memory",
                    project,
                    [],
                    [],
                    intent="teach_reject",
                )
            if (
                teach_flow.get("awaiting_confirmation")
                or intent in {"edit", "remind"}
                or teach_flow.get("pending")
            ):
                return _result(
                    _clean_response(reply or "Candidate memories ready for confirmation."),
                    "memory",
                    project,
                    teach_flow.get("memories")
                    or (teach_flow.get("pending") or {}).get("candidate_memories")
                    or [],
                    [],
                    intent="teach_pending",
                )

    if is_project_name_question(text):
        if project:
            reply = (
                f"Your active project is {project.repo_full_name}.\n\n"
                "This is the repository I'm using for memory, commits, and analysis.\n"
                "Use Teach Kassandra for guided knowledge-gap questions, or tell me "
                "institutional context here — I'll confirm before saving to Sibyl."
            )
        else:
            reply = "No active project selected. Add one under Projects."
        return _result(reply, "system", project, [], [])

    memory_hits = (
        _search_memory(tenant_id, text)
        if sibyl_enabled and _should_search_memory(text)
        else []
    )
    memory_block = _format_memory_context(memory_hits, sibyl_enabled=sibyl_enabled)

    if not project or not user.github_access_token:
        return _result(
            "I need an active GitHub project to answer that. Add one under Projects.",
            "system",
            project,
            [],
            [],
        )

    # First + last commit endpoints — authoritative GitHub history
    if is_commit_endpoints_question(text):
        try:
            endpoints_ctx = await fetch_commit_endpoints_context(
                user.github_access_token, project
            )
            first_detail = endpoints_ctx["first"]
            latest = endpoints_ctx.get("latest")
            evidence = endpoints_ctx.get("evidence") or []
            branch = endpoints_ctx.get("branch", project.default_branch or "main")

            if not is_llm_configured():
                reply = _clean_response(
                    answer_commit_endpoints_without_llm(
                        first_detail,
                        latest,
                        branch=branch,
                        total_commits=endpoints_ctx.get("total_commits"),
                    )
                )
                return _result(
                    reply, "github", project, memory_hits, evidence,
                    last_commit_sha=(latest.get("sha") or latest.get("id")) if latest else last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                )

            context_parts = [
                f"Sibyl project memory:\n{memory_block}",
                "Repository commit endpoints (retrieved from GitHub — use exactly as provided):\n"
                + endpoints_ctx["formatted"],
            ]
            messages = _build_llm_messages(repo_label, context_parts, history, text)
            try:
                reply = _clean_response(await chat_completion(messages))
                latest_sha = (latest.get("sha") or latest.get("id")) if latest else None
                return _result(
                    reply, "llm", project, memory_hits, evidence,
                    last_commit_sha=latest_sha or last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                )
            except LLMError:
                reply = _clean_response(
                    answer_commit_endpoints_without_llm(
                        first_detail,
                        latest,
                        branch=branch,
                        total_commits=endpoints_ctx.get("total_commits"),
                    )
                )
                latest_sha = (latest.get("sha") or latest.get("id")) if latest else None
                return _result(
                    reply, "github_fallback", project, memory_hits, evidence,
                    last_commit_sha=latest_sha or last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Commit endpoints lookup failed: %s", exc)

    # First commit — authoritative history traversal, not conversation memory
    if is_first_commit_question(text):
        try:
            first_ctx = await fetch_first_commit_context(
                user.github_access_token, project
            )
            detail = first_ctx["commit"]
            evidence = first_ctx.get("evidence") or []
            branch = first_ctx.get("branch", project.default_branch or "main")

            if not is_llm_configured():
                reply = _clean_response(
                    answer_first_commit_without_llm(
                        detail,
                        branch=branch,
                        total_commits=first_ctx.get("total_commits"),
                    )
                )
                return _result(
                    reply, "github", project, memory_hits, evidence,
                    last_commit_sha=last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                )

            context_parts = [
                f"Sibyl project memory:\n{memory_block}",
                "First commit on branch (retrieved from GitHub — use exactly as provided):\n"
                + first_ctx["formatted"],
            ]
            messages = _build_llm_messages(repo_label, context_parts, history, text)
            try:
                reply = _clean_response(await chat_completion(messages))
                return _result(
                    reply, "llm", project, memory_hits, evidence,
                    last_commit_sha=last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                )
            except LLMError:
                reply = _clean_response(
                    answer_first_commit_without_llm(
                        detail,
                        branch=branch,
                        total_commits=first_ctx.get("total_commits"),
                    )
                )
                return _result(
                    reply, "github_fallback", project, memory_hits, evidence,
                    last_commit_sha=last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("First commit lookup failed: %s", exc)

    # Previous commit lookup (before detail/compare so context is established)
    if is_previous_commit_question(text):
        try:
            ctx = await gather_chat_context(user.github_access_token, project, text)
            reply, prev_sha = answer_previous_commit(ctx, stored_commit_sha)
            if prev_sha:
                previous_commit_sha = prev_sha
            branch = ctx.get("branch", "main")
            evidence = previous_commit_evidence(prev_sha, branch, project.repo_full_name)
            return _result(
                _clean_response(reply),
                "github",
                project,
                memory_hits,
                evidence,
                last_commit_sha=last_commit_sha,
                previous_commit_sha=previous_commit_sha,
                sibyl_enabled=sibyl_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Previous commit lookup failed: %s", exc)

    # Parent commit lookup
    if is_parent_commit_question(text):
        try:
            sha = extract_commit_sha(
                text, history, stored_commit_sha, stored_previous_commit_sha
            )
            if not sha:
                ctx = await gather_chat_context(user.github_access_token, project, text)
                sha = get_latest_commit_sha(ctx)
            if sha:
                commit_ctx = await fetch_commit_context(
                    user.github_access_token, project, sha
                )
                detail = commit_ctx["commit"]
                branch = project.default_branch or "main"
                reply = _clean_response(answer_parent_commit(detail, branch=branch))
                return _result(
                    reply, "github", project, memory_hits, commit_ctx.get("evidence") or [],
                    last_commit_sha=last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parent commit lookup failed: %s", exc)

    # Commit comparison — always retrieve required commits from GitHub
    commit_targets = resolve_commit_targets(
        text,
        history,
        stored_sha=stored_commit_sha,
        stored_previous_sha=stored_previous_commit_sha,
    )
    compare_intent = commit_targets.get("intent")
    recent_n = parse_recent_commit_count(text) or commit_targets.get("count")

    if compare_intent in ("compare", "multi_compare") or (
        is_commit_compare_question(text) and recent_n
    ):
        try:
            shas = list(commit_targets.get("shas") or [])
            needed = recent_n if recent_n else (len(shas) if len(shas) >= 2 else 2)

            if recent_n or len(shas) < needed:
                shas = await fetch_recent_commit_shas(
                    user.github_access_token, project, needed
                )

            if len(shas) >= 3:
                compare_ctx = await fetch_multi_compare_context(
                    user.github_access_token, project, shas
                )
                commits = compare_ctx["commits"]
                evidence = compare_ctx.get("evidence") or []
                last_commit_sha = commits[0].get("sha") or shas[0]
                if len(commits) > 1:
                    previous_commit_sha = commits[1].get("sha") or shas[1]

                if not is_llm_configured():
                    reply = _clean_response(
                        answer_multi_commit_compare_without_llm(commits)
                    )
                    return _result(
                        reply, "github", project, memory_hits, evidence,
                        last_commit_sha=last_commit_sha,
                        previous_commit_sha=previous_commit_sha,
                        sibyl_enabled=sibyl_enabled,
                    )

                context_parts = [
                    f"Sibyl project memory:\n{memory_block}",
                    "Compare these commits (freshly retrieved from GitHub). "
                    "Do NOT say you only have previously supplied data.\n\n"
                    + compare_ctx["formatted"],
                ]
                messages = _build_llm_messages(repo_label, context_parts, history, text)
                try:
                    raw = await chat_completion(messages)
                    reply = _finalize_llm_reply(
                        raw,
                        history=history,
                        extra_contexts=commits,
                    )
                    return _result(
                        reply, "llm", project, memory_hits, evidence,
                        last_commit_sha=last_commit_sha,
                        previous_commit_sha=previous_commit_sha,
                        sibyl_enabled=sibyl_enabled,
                    )
                except LLMError:
                    reply = _clean_response(
                        answer_multi_commit_compare_without_llm(commits)
                    )
                    return _result(
                        reply, "github_fallback", project, memory_hits, evidence,
                        last_commit_sha=last_commit_sha,
                        previous_commit_sha=previous_commit_sha,
                        sibyl_enabled=sibyl_enabled,
                    )

            if len(shas) >= 2:
                sha_a, sha_b = shas[0], shas[1]
                compare_ctx = await fetch_compare_context(
                    user.github_access_token, project, sha_a, sha_b
                )
                detail_a = compare_ctx["commit_a"]
                detail_b = compare_ctx["commit_b"]
                evidence = compare_ctx.get("evidence") or []
                last_commit_sha = detail_a.get("sha") or sha_a
                previous_commit_sha = detail_b.get("sha") or sha_b

                if not is_llm_configured():
                    reply = _clean_response(
                        answer_commit_compare_without_llm(detail_a, detail_b)
                    )
                    return _result(
                        reply, "github", project, memory_hits, evidence,
                        last_commit_sha=last_commit_sha,
                        previous_commit_sha=previous_commit_sha,
                        sibyl_enabled=sibyl_enabled,
                    )

                context_parts = [
                    f"Sibyl project memory:\n{memory_block}",
                    "Compare these two commits (freshly retrieved from GitHub). "
                    "Use the FILE SUMMARY counts exactly as given.\n"
                    "Never mix total changed counts with unique-only counts.\n\n"
                    + compare_ctx["formatted"],
                ]
                messages = _build_llm_messages(repo_label, context_parts, history, text)
                try:
                    reply = _clean_response(await chat_completion(messages))
                    return _result(
                        reply, "llm", project, memory_hits, evidence,
                        last_commit_sha=last_commit_sha,
                        previous_commit_sha=previous_commit_sha,
                        sibyl_enabled=sibyl_enabled,
                    )
                except LLMError:
                    reply = _clean_response(
                        answer_commit_compare_without_llm(detail_a, detail_b)
                    )
                    return _result(
                        reply, "github_fallback", project, memory_hits, evidence,
                        last_commit_sha=last_commit_sha,
                        previous_commit_sha=previous_commit_sha,
                        sibyl_enabled=sibyl_enabled,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Commit comparison failed: %s", exc)

    # Commit-specific retrieval (file list, diff, change analysis)
    wants_commit_detail = (
        is_commit_change_question(text)
        or is_commit_file_list_question(text)
        or mentions_commit_sha(text)
        or should_fetch_commit_detail(text)
    )
    if wants_commit_detail:
        sha = extract_commit_sha(
            text, history, stored_commit_sha, stored_previous_commit_sha
        )
        if not sha:
            ctx = await gather_chat_context(user.github_access_token, project, text)
            sha = get_latest_commit_sha(ctx)

        if sha:
            commit_ctx = await fetch_commit_context(
                user.github_access_token, project, sha
            )
            detail = commit_ctx["commit"]
            evidence = commit_ctx.get("evidence") or []
            detail_sha = detail.get("sha") or sha

            if stored_commit_sha and detail_sha[:7].lower() == stored_commit_sha[:7].lower():
                last_commit_sha = detail_sha
            elif stored_previous_commit_sha and detail_sha[:7].lower() == stored_previous_commit_sha[:7].lower():
                previous_commit_sha = detail_sha
            elif stored_commit_sha:
                previous_commit_sha = detail_sha
            else:
                last_commit_sha = detail_sha

            stored_validation = validate_canonical_sha(stored_commit_sha, detail_sha)
            if stored_validation.get("conflict"):
                logger.warning(
                    "SHA conflict for %s: stored=%s canonical=%s",
                    detail_sha[:7],
                    stored_commit_sha,
                    detail_sha,
                )

            annotations = build_commit_context_annotations(
                history, text, detail, deep_retrieval=True
            )
            formatted = commit_ctx["formatted"]
            if annotations:
                formatted = formatted + "\n\n" + annotations

            discrepancy_notes = [
                n for n in annotations.split("\n\n") if n.startswith("DISCREPANCY")
            ] if annotations else []
            correction_preamble = build_self_correction_preamble(discrepancy_notes)

            escalation_preamble: str | None = None
            if find_prior_unavailability_claim(history, detail):
                escalation_preamble = format_evidence_escalation_note(
                    prior_unavailable=True,
                    deep_retrieval=True,
                    file_count=detail.get("file_count")
                    or len(detail.get("files") or []),
                )

            combined_preamble = correction_preamble or escalation_preamble
            if correction_preamble and escalation_preamble:
                combined_preamble = correction_preamble + "\n\n" + escalation_preamble

            if is_commit_file_list_question(text) and not is_commit_change_question(text):
                branch = project.default_branch or "main"
                reply = _prepend_preamble(
                    answer_commit_file_list(detail, branch=branch),
                    combined_preamble,
                )
                return _result(
                    _clean_response(reply), "github", project, memory_hits, evidence,
                    last_commit_sha=last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                    has_commit_detail=True,
                )

            if not is_llm_configured():
                reply = _prepend_preamble(
                    answer_commit_changes_without_llm(detail, memory_block),
                    combined_preamble,
                )
                return _result(
                    _clean_response(reply), "github", project, memory_hits, evidence,
                    last_commit_sha=last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                    has_commit_detail=True,
                )

            memory_conflicts = _memory_conflict_block(memory_hits)
            context_parts = [
                f"Sibyl project memory:\n{memory_block}",
            ]
            if memory_conflicts:
                context_parts.append(memory_conflicts)
            context_parts.append(
                "Analyze ONLY this specific commit (not other recent commits):\n" + formatted
            )
            messages = _build_llm_messages(repo_label, context_parts, history, text)
            try:
                reply = _finalize_llm_reply(
                    await chat_completion(messages),
                    history=history,
                    detail=detail,
                )
                reply = _prepend_preamble(reply, combined_preamble)
                return _result(
                    reply, "llm", project, memory_hits, evidence,
                    last_commit_sha=last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                    has_commit_detail=True,
                )
            except LLMError:
                reply = _prepend_preamble(
                    answer_commit_changes_without_llm(detail, memory_block),
                    combined_preamble,
                )
                return _result(
                    _clean_response(reply), "github_fallback", project, memory_hits, evidence,
                    last_commit_sha=last_commit_sha,
                    previous_commit_sha=previous_commit_sha,
                    sibyl_enabled=sibyl_enabled,
                    has_commit_detail=True,
                )

    # File/function historical tracing
    if is_file_history_question(text):
        try:
            hist_ctx = await fetch_file_history_context(
                user.github_access_token, project, text
            )
            evidence = hist_ctx.get("evidence") or []
            reply = _clean_response(answer_file_history(hist_ctx))
            return _result(
                reply,
                "github",
                project,
                memory_hits,
                evidence,
                sibyl_enabled=sibyl_enabled,
                has_repo_history=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("File history trace failed: %s", exc)

    # Direct GitHub stats answers (commit count, contributors)
    if is_commit_count_question(text) or is_contributor_question(text):
        try:
            stats = await gather_repo_stats(user.github_access_token, project)
            evidence = repo_stats_evidence_refs(stats)
            stats_note = find_stats_discrepancy(history, stats)
            stats_notes = [stats_note] if stats_note else []
            memory_conflicts = _memory_conflict_block(memory_hits, stats=stats)
            if memory_conflicts:
                stats_notes.extend(memory_conflicts.split("\n\n"))
            stats_preamble = build_self_correction_preamble(stats_notes)

            if is_commit_count_question(text) and not is_contributor_question(text):
                reply = _prepend_preamble(answer_commit_count(stats), stats_preamble)
                return _result(
                    _clean_response(reply), "github", project, memory_hits, evidence,
                    sibyl_enabled=sibyl_enabled, has_repo_history=True,
                )

            if is_contributor_question(text) and not is_commit_count_question(text):
                reply = _prepend_preamble(answer_contributor_count(stats), stats_preamble)
                return _result(
                    _clean_response(reply), "github", project, memory_hits, evidence,
                    sibyl_enabled=sibyl_enabled, has_repo_history=True,
                )

            reply = _prepend_preamble(
                answer_commit_count(stats) + "\n\n" + answer_contributor_count(stats),
                stats_preamble,
            )
            return _result(
                _clean_response(reply), "github", project, memory_hits, evidence,
                sibyl_enabled=sibyl_enabled, has_repo_history=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Repo stats fetch failed: %s", exc)

    # Repo creation date
    if is_repo_created_question(text):
        try:
            repo_meta = await get_repo(user.github_access_token, project.repo_full_name)
            reply = _clean_response(answer_repo_created(repo_meta, project.repo_full_name))
            return _result(
                reply,
                "github",
                project,
                memory_hits,
                repo_created_evidence(
                    project.repo_full_name, repo_meta.get("created_at", "")
                ),
                sibyl_enabled=sibyl_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Repo metadata fetch failed: %s", exc)

    # Most-changed files analysis
    if is_file_churn_question(text):
        try:
            churn = await analyze_file_churn(
                user.github_access_token,
                project.repo_full_name,
                branch=project.default_branch or "main",
            )
            reply = _clean_response(answer_file_churn(churn, project.repo_full_name))
            evidence = file_churn_evidence(churn, project.repo_full_name)
            return _result(
                reply, "github", project, memory_hits, evidence, sibyl_enabled=sibyl_enabled
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("File churn analysis failed: %s", exc)

    # Direct GitHub activity answers (deployments, CI, releases, overview)
    if (
        is_deployment_question(text)
        or is_ci_question(text)
        or is_release_question(text)
        or is_activity_overview_question(text)
    ):
        try:
            repo_ctx = await gather_chat_context(
                user.github_access_token, project, text
            )
            activity = repo_ctx.get("repo_activity") or {}

            if is_activity_overview_question(text):
                reply = _clean_response(
                    answer_activity_overview(activity, repo_ctx, memory_block)
                )
                return _result(
                    reply,
                    "github",
                    project,
                    memory_hits,
                    activity_overview_evidence(repo_ctx),
                    sibyl_enabled=sibyl_enabled,
                )

            if is_deployment_question(text) and not is_ci_question(text):
                reply = _clean_response(
                    answer_deployments(activity, project.repo_full_name)
                )
                return _result(
                    reply,
                    "github",
                    project,
                    memory_hits,
                    deployment_evidence(project.repo_full_name),
                    sibyl_enabled=sibyl_enabled,
                )

            if is_ci_question(text) and not is_deployment_question(text):
                reply = _clean_response(
                    answer_ci_status(activity, project.repo_full_name)
                )
                return _result(
                    reply,
                    "github",
                    project,
                    memory_hits,
                    ci_evidence(project.repo_full_name, activity.get("workflow_runs")),
                    sibyl_enabled=sibyl_enabled,
                )

            if is_release_question(text):
                reply = _clean_response(
                    answer_releases(activity, project.repo_full_name)
                )
                return _result(
                    reply,
                    "github",
                    project,
                    memory_hits,
                    release_evidence(project.repo_full_name),
                    sibyl_enabled=sibyl_enabled,
                )

            reply = _clean_response(
                answer_ci_status(activity, project.repo_full_name)
                + "\n\n"
                + answer_deployments(activity, project.repo_full_name)
            )
            return _result(
                reply,
                "github",
                project,
                memory_hits,
                merge_evidence(
                    ci_evidence(project.repo_full_name, activity.get("workflow_runs")),
                    deployment_evidence(project.repo_full_name),
                ),
                sibyl_enabled=sibyl_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Repo activity fetch failed: %s", exc)

    repo_ctx: dict | None = None
    evidence_refs: list = []

    try:
        repo_ctx = await gather_chat_context(user.github_access_token, project, text)
        evidence_block = format_context_for_llm(repo_ctx)
        evidence_refs = build_question_evidence(text, repo_ctx, project.repo_full_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Repo context gathering failed: %s", exc)
        evidence_block = f"Repository inspection failed: {exc}"

    if repo_ctx and is_last_commit_author_question(text):
        reply, sha = answer_last_commit_author(repo_ctx)
        last_commit_sha = sha
        previous_commit_sha = get_previous_commit_sha(repo_ctx, sha) or previous_commit_sha
        evidence = last_commit_author_evidence(
            sha, repo_ctx.get("branch", "main"), project.repo_full_name
        )
        return _result(
            _clean_response(reply or ""),
            "github",
            project,
            memory_hits,
            evidence,
            last_commit_sha=last_commit_sha,
            previous_commit_sha=previous_commit_sha,
            sibyl_enabled=sibyl_enabled,
        )

    if repo_ctx and is_recent_changes_question(text) and not is_llm_configured():
        reply = _clean_response(answer_recent_changes(repo_ctx, memory_block))
        return _result(
            reply,
            "github",
            project,
            memory_hits,
            recent_changes_evidence(repo_ctx),
            sibyl_enabled=sibyl_enabled,
        )

    if not is_llm_configured():
        parts = [
            f"Active project: {repo_label}",
            f"Verified from repository:\n{evidence_block}",
            f"From Sibyl project memory:\n{memory_block}",
            "Configure LLM in server/.env for full AI-generated answers.",
        ]
        return _result(
            _clean_response("\n\n".join(parts)),
            "memory_only",
            project,
            memory_hits,
            evidence_refs,
            sibyl_enabled=sibyl_enabled,
        )

    context_parts = [
        f"Sibyl project memory:\n{memory_block}",
        f"Repository evidence (pre-fetched from GitHub — use this only):\n{evidence_block}",
    ]
    memory_conflicts = _memory_conflict_block(
        memory_hits,
        stats=repo_ctx.get("repo_stats") if repo_ctx else None,
        latest_author=(
            (repo_ctx.get("commits") or [{}])[0].get("author")
            if repo_ctx and repo_ctx.get("commits")
            else None
        ),
        latest_sha=(
            (repo_ctx.get("commits") or [{}])[0].get("sha")
            if repo_ctx and repo_ctx.get("commits")
            else None
        ),
    )
    if memory_conflicts:
        context_parts.append(memory_conflicts)
    if history:
        context_parts.append(
            "Recent conversation:\n"
            + "\n".join(f"{m['role']}: {m['content'][:300]}" for m in history[-6:])
        )

    messages = _build_llm_messages(repo_label, context_parts, history, text)

    try:
        reply = _finalize_llm_reply(
            await chat_completion(messages),
            history=history,
            detail=repo_ctx.get("commit_detail") if repo_ctx else None,
            extra_contexts=[repo_ctx.get("commits") if repo_ctx else None],
        )
        source = "llm"
    except LLMError as exc:
        if repo_ctx and is_recent_changes_question(text):
            reply = _clean_response(answer_recent_changes(repo_ctx, memory_block))
            source = "github_fallback"
        else:
            reply = _clean_response(
                f"I couldn't reach the LLM ({exc.message}).\n\n{memory_block}"
            )
            source = "memory_fallback"

    return _result(
        reply, source, project, memory_hits, evidence_refs,
        last_commit_sha=last_commit_sha,
        previous_commit_sha=previous_commit_sha,
        sibyl_enabled=sibyl_enabled,
        has_repo_history=bool(repo_ctx),
        has_commit_detail=bool(repo_ctx and repo_ctx.get("commit_detail")),
    )


def _result(
    reply: str,
    source: str,
    project: Project | None,
    memory_hits: list,
    evidence: list,
    intent: str | None = None,
    last_commit_sha: str | None = None,
    previous_commit_sha: str | None = None,
    *,
    sibyl_enabled: bool = True,
    has_commit_detail: bool = False,
    has_repo_history: bool = False,
    is_session: bool = False,
    evidence_level: EvidenceLevel | None = None,
    candidate_note: str | None = None,
) -> dict:
    github_evidence = normalize_evidence(evidence)
    if sibyl_enabled and memory_hits:
        final_evidence = merge_evidence(github_evidence, sibyl_memory_evidence(memory_hits))
    else:
        final_evidence = github_evidence

    level = evidence_level or infer_evidence_level(
        source,
        has_commit_detail=has_commit_detail,
        has_repo_history=has_repo_history,
        is_session=is_session,
    )

    final_reply = reply
    if candidate_note and candidate_note not in final_reply:
        final_reply = f"{final_reply.rstrip()}\n\n{candidate_note}"

    return {
        "reply": final_reply,
        "source": source,
        "intent": intent,
        "project_id": project.id if project else None,
        "memory_hits": len(memory_hits) if isinstance(memory_hits, list) else memory_hits,
        "evidence": final_evidence,
        "last_commit_sha": last_commit_sha,
        "previous_commit_sha": previous_commit_sha,
        "evidence_level": int(level),
        "evidence_level_name": level.name,
    }


def get_initial_chat_message(
    user_name: str | None = None,
    *,
    repo_full_name: str | None = None,
    gap_count: int = 0,
) -> str:
    return get_welcome_message(
        user_name,
        repo_full_name=repo_full_name,
        gap_count=gap_count,
    )
