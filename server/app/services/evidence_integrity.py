"""Evidence integrity — identifier validation, escalation, and discrepancy detection.

Implements reliability requirements from the Kassandra conversation review:
- Never synthesize identifiers (especially commit SHAs)
- Canonical identifier validation against authoritative GitHub data
- Evidence escalation with user-facing explanation
- Distinguish unavailable evidence from missing facts
- Contradiction detection and self-correction prompts
"""

from __future__ import annotations

import re
from enum import Enum, IntEnum
from typing import Any

FULL_SHA_RE = re.compile(r"\b([0-9a-f]{40})\b", re.I)
SHORT_SHA_RE = re.compile(r"\b([0-9a-f]{7,39})\b", re.I)
FILE_PATH_RE = re.compile(
    r"(?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|php|cs|cpp|c|h|md|json|yaml|yml|toml|sql|sh)"
    r"|(?:^|\s)([\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|php|cs|md|json))\b",
    re.I,
)

_UNAVAILABLE_PATTERNS = [
    re.compile(r"cannot be enumerated from the available evidence", re.I),
    re.compile(r"file list.{0,40}unavailable", re.I),
    re.compile(r"did not (?:return|include).{0,40}file", re.I),
    re.compile(r"no (?:changed[- ]file|file) (?:list|manifest)", re.I),
    re.compile(r"specific files changed cannot", re.I),
    re.compile(r"could not retrieve file changes", re.I),
    re.compile(r"without a diff.{0,60}enumerate", re.I),
]

_FETCH_ESCALATION_PATTERNS = [
    re.compile(r"\b(fetch|check|get|retrieve|look up|pull)\b", re.I),
    re.compile(r"\bfile list\b", re.I),
    re.compile(r"\bchanged files?\b", re.I),
    re.compile(r"\bcan you\b", re.I),
]


class EvidenceLevel(IntEnum):
    """Explicit evidence-retrieval levels (review §5)."""

    CONVERSATION_MEMORY = 1
    STORED_REPOSITORY_EVIDENCE = 2
    REPOSITORY_HISTORY = 3
    DEEP_COMMIT_RETRIEVAL = 4
    UNKNOWN = 5


class EvidenceState(str, Enum):
    """Distinguish evidence availability states (review §6)."""

    VERIFIED = "verified"
    NOT_RETRIEVED = "not_retrieved"
    INCOMPLETE = "incomplete"
    CONFLICT = "conflict"
    NOT_FOUND = "not_found"
    ACCESS_ERROR = "access_error"


def short_sha(sha: str) -> str:
    return sha[:7].lower()


def is_full_sha(sha: str) -> bool:
    return bool(sha) and len(sha) == 40 and bool(FULL_SHA_RE.fullmatch(sha))


def format_commit_sha_display(detail: dict) -> str:
    """Use canonical full SHA from GitHub when available; otherwise short SHA only."""
    canonical = detail.get("sha") or ""
    if is_full_sha(canonical):
        return canonical
    short = detail.get("short_sha") or canonical[:7]
    return short or "unknown"


def validate_canonical_sha(
    cited_sha: str | None,
    canonical_sha: str,
) -> dict[str, str | bool | None]:
    """Check whether a cited SHA matches authoritative GitHub data."""
    if not canonical_sha:
        return {"valid": False, "conflict": False, "message": "No canonical SHA available."}
    if not cited_sha:
        return {"valid": True, "conflict": False, "message": None}

    cited = cited_sha.strip().lower()
    canonical = canonical_sha.strip().lower()

    if cited == canonical:
        return {"valid": True, "conflict": False, "message": None}

    if len(cited) < 40 and canonical.startswith(cited[:7]):
        return {"valid": True, "conflict": False, "message": None}

    if len(cited) == 40 and canonical.startswith(cited[:7]) and cited != canonical:
        return {
            "valid": False,
            "conflict": True,
            "message": (
                f"DISCREPANCY NOTE: A prior response cited full SHA {cited}, but "
                f"authoritative GitHub data returns {canonical}. Prefer the GitHub "
                f"SHA and correct the earlier answer if the user asks."
            ),
        }

    if len(cited) >= 7 and not canonical.startswith(cited[:7]):
        return {
            "valid": False,
            "conflict": True,
            "message": (
                f"DISCREPANCY NOTE: Cited SHA {cited[:7]} does not match "
                f"authoritative GitHub SHA {canonical[:7]}. Re-query GitHub and "
                f"use the canonical value."
            ),
        }

    return {"valid": True, "conflict": False, "message": None}


def _assistant_messages(history: list[dict[str, str]]) -> list[str]:
    return [
        msg.get("content") or ""
        for msg in history
        if msg.get("role") == "assistant"
    ]


def find_sha_discrepancy(
    history: list[dict[str, str]],
    detail: dict,
) -> str | None:
    """Detect conflicting full SHAs for the same short prefix in conversation history."""
    canonical = (detail.get("sha") or "").lower()
    if not is_full_sha(canonical):
        return None

    prefix = short_sha(canonical)
    seen_full: set[str] = set()

    for content in _assistant_messages(history):
        if prefix not in content.lower():
            continue
        for match in FULL_SHA_RE.finditer(content):
            cited = match.group(1).lower()
            if cited.startswith(prefix) and cited != canonical:
                seen_full.add(cited)

    if not seen_full:
        return None

    prior = sorted(seen_full)[0]
    return (
        f"DISCREPANCY NOTE: Earlier in this conversation, full SHA {prior} was reported "
        f"for commit {prefix}. Authoritative GitHub data returns {canonical}. "
        f"Never synthesize SHA characters — use the GitHub canonical SHA and "
        f"acknowledge the correction if asked."
    )


def find_prior_unavailability_claim(
    history: list[dict[str, str]],
    detail: dict,
) -> bool:
    """True when a prior assistant reply claimed file-level evidence was unavailable."""
    prefix = short_sha(detail.get("short_sha") or detail.get("sha") or "")
    if not prefix:
        return False

    file_count = detail.get("file_count") or len(detail.get("files") or [])
    if not file_count:
        return False

    for content in _assistant_messages(history):
        if prefix not in content.lower():
            continue
        if any(p.search(content) for p in _UNAVAILABLE_PATTERNS):
            return True
    return False


def format_evidence_escalation_note(
    *,
    prior_unavailable: bool,
    deep_retrieval: bool,
    file_count: int | None = None,
) -> str | None:
    """User-facing note when evidence depth increased (review §2, §5, §6)."""
    if not deep_retrieval:
        return None

    if prior_unavailable and file_count:
        return (
            f"EVIDENCE ESCALATION: The earlier response only had commit metadata without "
            f"a complete file manifest. I queried the commit directly on GitHub and "
            f"retrieved {file_count} changed file{'s' if file_count != 1 else ''}."
        )

    if prior_unavailable:
        return (
            "EVIDENCE ESCALATION: The earlier response only had commit metadata. "
            "I performed a deeper commit-level retrieval on GitHub."
        )

    return None


def should_explain_escalation(message: str, history: list[dict[str, str]], detail: dict) -> bool:
    """Whether the user is asking for deeper evidence after a shallow prior answer."""
    if find_prior_unavailability_claim(history, detail):
        return True
    if any(p.search(message) for p in _FETCH_ESCALATION_PATTERNS):
        return any(p.search(msg) for msg in _assistant_messages(history) for p in _UNAVAILABLE_PATTERNS)
    return False


def collect_known_shas(*contexts: dict | list[dict] | None) -> dict[str, str]:
    """Map short SHA prefix → canonical full SHA from evidence contexts."""
    known: dict[str, str] = {}
    for ctx in contexts:
        items: list[dict] = []
        if isinstance(ctx, list):
            items = [i for i in ctx if isinstance(i, dict)]
        elif isinstance(ctx, dict):
            if ctx.get("sha"):
                items = [ctx]
            elif ctx.get("commit"):
                items = [ctx["commit"]]
            elif ctx.get("commits"):
                items = [c for c in ctx["commits"] if isinstance(c, dict)]
            elif ctx.get("commit_detail"):
                items = [ctx["commit_detail"]]

        for item in items:
            sha = item.get("sha") or ""
            if is_full_sha(sha):
                known[short_sha(sha)] = sha.lower()
    return known


def collect_known_file_paths(*contexts: dict | list[dict] | None) -> set[str]:
    """Collect file paths present in commit manifests."""
    paths: set[str] = set()
    for ctx in contexts:
        details: list[dict] = []
        if isinstance(ctx, dict):
            if ctx.get("files"):
                details = [ctx]
            elif ctx.get("commit"):
                details = [ctx["commit"]]
            elif ctx.get("commit_detail"):
                details = [ctx["commit_detail"]]
        for detail in details:
            for f in detail.get("files") or []:
                path = f.get("filename")
                if path:
                    paths.add(path)
            for path in detail.get("all_filenames") or []:
                paths.add(path)
    return paths


def sanitize_llm_reply(
    reply: str,
    *,
    known_shas: dict[str, str],
    history: list[dict[str, str]] | None = None,
) -> str:
    """Replace synthesized full SHAs with canonical values from evidence."""
    if not reply or not known_shas:
        return reply

    corrected = reply
    replacements: list[str] = []

    for match in FULL_SHA_RE.finditer(reply):
        cited = match.group(1).lower()
        prefix = short_sha(cited)
        canonical = known_shas.get(prefix)
        if canonical and cited != canonical:
            corrected = corrected.replace(match.group(1), canonical)
            replacements.append(
                f"full SHA {cited} → {canonical} (canonical from GitHub)"
            )

    if replacements and history is not None:
        # Only prepend correction when we actually fixed something material
        unique = list(dict.fromkeys(replacements))
        if unique and "Correction:" not in corrected[:120]:
            preamble = (
                "Correction: I replaced synthesized commit SHA(s) with the "
                f"canonical GitHub value(s): {', '.join(unique[:2])}."
            )
            if len(unique) > 2:
                preamble += f" ({len(unique) - 2} more corrected.)"
            corrected = preamble + "\n\n" + corrected

    return corrected


def find_author_discrepancy(
    history: list[dict[str, str]],
    detail: dict,
) -> str | None:
    """Detect when a prior assistant message reported a different author for this SHA."""
    sha = short_sha(detail.get("short_sha") or detail.get("sha") or "")
    author = (detail.get("author") or "").strip()
    if not sha or not author:
        return None

    author_pattern = re.compile(
        rf"\b{re.escape(sha)}\b[^\n]{{0,160}}?\b(?:by|author[:\s]+)\s*([A-Za-z0-9_-]+)",
        re.I,
    )
    alt_pattern = re.compile(
        rf"(?:author|made by|written by)[:\s]+([A-Za-z0-9_-]+)[^\n]{{0,160}}?\b{re.escape(sha)}\b",
        re.I,
    )

    for content in _assistant_messages(history):
        if sha not in content.lower():
            continue
        for pattern in (author_pattern, alt_pattern):
            match = pattern.search(content)
            if match:
                prior = match.group(1).strip()
                if prior.lower() != author.lower():
                    return (
                        f"DISCREPANCY NOTE: Earlier in this conversation, commit {sha} "
                        f"was attributed to {prior}. Authoritative GitHub data shows "
                        f"{author}. Prefer the GitHub author metadata."
                    )
    return None


def find_stats_discrepancy(
    history: list[dict[str, str]],
    stats: dict,
) -> str | None:
    """Detect when conversation claims conflict with GitHub repo stats."""
    branch = stats.get("branch", "main")
    commit_count = stats.get("commit_count")
    contributor_count = stats.get("contributor_count")
    if commit_count is None and contributor_count is None:
        return None

    for content in _assistant_messages(history):
        if commit_count is not None:
            for pattern in (
                re.compile(
                    rf"\b(\d+)\s+commits?\b[^\n]{{0,80}}?\b{re.escape(branch)}\b",
                    re.I,
                ),
                re.compile(
                    rf"\b{re.escape(branch)}\b[^\n]{{0,80}}?\b(\d+)\s+commits?\b",
                    re.I,
                ),
            ):
                match = pattern.search(content)
                if match:
                    prior = int(match.group(1))
                    if prior != commit_count:
                        return (
                            f"DISCREPANCY NOTE: Earlier in this conversation, {prior} commits "
                            f"were reported on {branch}. Authoritative GitHub data shows "
                            f"{commit_count:,}. Prefer the GitHub count."
                        )
        if contributor_count is not None:
            for match in re.finditer(
                r"(?:only|single|one)\s+contributor",
                content,
                re.I,
            ):
                if contributor_count != 1:
                    return (
                        f"DISCREPANCY NOTE: Earlier in this conversation, the repository was "
                        f"described as having a single contributor. GitHub's contributors "
                        f"API shows {contributor_count} distinct contributors repository-wide."
                    )
    return None


def find_memory_git_conflicts(
    memory_hits: list[Any],
    *,
    stats: dict | None = None,
    latest_author: str | None = None,
    latest_sha: str | None = None,
) -> list[str]:
    """Flag when Sibyl memory claims may conflict with GitHub evidence (review §11–12)."""
    if not memory_hits:
        return []

    notes: list[str] = []
    memory_text = " ".join(
        str(h.get("content") or h.get("text") or h) if isinstance(h, dict) else str(h)
        for h in memory_hits[:10]
    ).lower()

    if stats:
        commit_count = stats.get("commit_count")
        contributor_count = stats.get("contributor_count")
        branch = stats.get("branch", "main")

        if commit_count is not None:
            for match in re.finditer(r"\b(\d+)\s+commits?\b", memory_text):
                claimed = int(match.group(1))
                if claimed != commit_count:
                    notes.append(
                        "MEMORY/GIT CONFLICT: Sibyl memory mentions "
                        f"{claimed} commits, but GitHub shows {commit_count:,} on "
                        f"{branch}. Git history is authoritative for WHAT happened; "
                        "use Sibyl memory only for WHY."
                    )
                    break

        if contributor_count is not None and contributor_count != 1:
            if re.search(r"\b(only|single|one)\s+contributor\b", memory_text):
                notes.append(
                    "MEMORY/GIT CONFLICT: Sibyl memory suggests a single contributor, "
                    f"but GitHub's contributors API shows {contributor_count} people "
                    "repository-wide. Do not equate branch-scoped history with "
                    "repo-wide contributor counts."
                )

    if latest_author and latest_sha:
        prefix = short_sha(latest_sha)
        if prefix in memory_text:
            for match in re.finditer(r"(?:by|author)\s+([a-z0-9_-]+)", memory_text):
                mem_author = match.group(1)
                if mem_author != latest_author.lower():
                    notes.append(
                        f"MEMORY/GIT CONFLICT: Sibyl memory references author "
                        f"{mem_author} near commit {prefix}, but GitHub shows "
                        f"{latest_author} as the latest commit author. Prefer GitHub "
                        "metadata for authorship."
                    )
                    break

    return notes


def build_self_correction_preamble(notes: list[str]) -> str | None:
    """Generate a user-facing correction preamble (review §13)."""
    if not notes:
        return None

    for note in notes:
        if note.startswith("DISCREPANCY NOTE:"):
            body = note.removeprefix("DISCREPANCY NOTE:").strip()
            return f"Correction: {body}"
        if note.startswith("MEMORY/GIT CONFLICT:"):
            body = note.removeprefix("MEMORY/GIT CONFLICT:").strip()
            return (
                "Correction: There is a conflict between institutional memory and "
                f"GitHub evidence. {body}"
            )
    return None


def build_evidence_discrepancy_notes(
    history: list[dict[str, str]],
    detail: dict,
) -> list[str]:
    """Collect all discrepancy notes for a commit detail response."""
    from app.services.repo_context import find_commit_count_discrepancy

    notes: list[str] = []

    count_note = find_commit_count_discrepancy(history, detail)
    if count_note:
        notes.append(count_note)

    sha_note = find_sha_discrepancy(history, detail)
    if sha_note and sha_note not in notes:
        notes.append(sha_note)

    author_note = find_author_discrepancy(history, detail)
    if author_note and author_note not in notes:
        notes.append(author_note)

    return notes


def infer_evidence_level(
    source: str,
    *,
    has_commit_detail: bool = False,
    has_repo_history: bool = False,
    is_session: bool = False,
) -> EvidenceLevel:
    """Map a response source to an evidence-retrieval level."""
    if is_session or source == "session":
        return EvidenceLevel.CONVERSATION_MEMORY
    if source == "memory_only" or source == "memory_fallback":
        return EvidenceLevel.STORED_REPOSITORY_EVIDENCE
    if has_commit_detail or source in ("github", "github_fallback") and has_commit_detail:
        return EvidenceLevel.DEEP_COMMIT_RETRIEVAL
    if source in ("github", "github_fallback", "llm") and has_repo_history:
        return EvidenceLevel.REPOSITORY_HISTORY
    if source == "llm":
        return EvidenceLevel.REPOSITORY_HISTORY
    return EvidenceLevel.UNKNOWN


def build_commit_context_annotations(
    history: list[dict[str, str]],
    message: str,
    detail: dict,
    *,
    deep_retrieval: bool = True,
) -> str:
    """Combine discrepancy and escalation annotations for LLM/direct commit answers."""
    parts: list[str] = []

    parts.extend(build_evidence_discrepancy_notes(history, detail))

    prior_unavailable = find_prior_unavailability_claim(history, detail)
    if should_explain_escalation(message, history, detail) or prior_unavailable:
        escalation = format_evidence_escalation_note(
            prior_unavailable=prior_unavailable,
            deep_retrieval=deep_retrieval,
            file_count=detail.get("file_count") or len(detail.get("files") or []),
        )
        if escalation:
            parts.append(escalation)

    return "\n\n".join(parts)
