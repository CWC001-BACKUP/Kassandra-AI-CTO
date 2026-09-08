"""Deep GitHub repository context for evidence-grounded chat."""

from __future__ import annotations

import json
import re

from app.services.commit_compare import (
    answer_commit_compare_without_llm,
    compare_commits,
    format_commit_compare_block,
)
from app.services.github_activity import (
    activity_evidence_sources,
    format_activity_for_llm,
    format_ci_logs_block,
    format_deployments_block,
    format_releases_block,
    format_workflow_runs_block,
    format_events_block,
    gather_repository_activity,
)
from app.services.github import (
    analyze_file_churn,
    build_repo_tree,
    count_commits,
    get_file_content,
    get_readme,
    get_repo,
    get_repo_languages,
    list_commits,
    list_contributors,
    list_directory,
    list_issues,
    list_pull_requests,
    list_root_files,
)

# Question intent patterns
COMMIT_HISTORY_PATTERN = re.compile(
    r"\b("
    r"commit|commits|who made|last commit|recent change|what changed|"
    r"changed recently|latest change|push|pushed|author|who wrote|"
    r"git log|history|recent work|recent activity|contributor|contributors|"
    r"how many people|how many commits|total commits"
    r")\b",
    re.IGNORECASE,
)

COMMIT_COUNT_PATTERN = re.compile(
    r"\b("
    r"how many commits|total commits|number of commits|commit count|"
    r"commits in total|commits are (there|in)|count.*commits"
    r")\b",
    re.IGNORECASE,
)

CONTRIBUTOR_PATTERN = re.compile(
    r"\b("
    r"how many contributors|number of contributors|contributor count|"
    r"how many people.*(commit|contributed|contribut)|"
    r"who (has |have )?contributed|list contributors|people.*commits"
    r")\b",
    re.IGNORECASE,
)

DEPLOYMENT_PATTERN = re.compile(
    r"\b("
    r"deploy|deployment|deployed|deploying|production deploy|staging deploy|"
    r"deployment (log|status|history)|what was deployed|last deploy"
    r")\b",
    re.IGNORECASE,
)

CI_PATTERN = re.compile(
    r"\b("
    r"ci\b|cd\b|pipeline|github actions?|workflow run|build (failed|status|log)|"
    r"test (failed|status)|ci\/cd|action run|deployment log|build log|"
    r"why did (the )?build fail|failed (build|pipeline|workflow)"
    r")\b",
    re.IGNORECASE,
)

RELEASE_PATTERN = re.compile(
    r"\b(releases?|version tag|tagged version|latest release|changelog)\b",
    re.IGNORECASE,
)

ACTIVITY_OVERVIEW_PATTERN = re.compile(
    r"\b("
    r"what(?:'s| is) going on|everything happening|repo activity|full overview|"
    r"project status|repository status|tell me everything|what happened|"
    r"recent activity|what(?:'s| is) happening"
    r")\b",
    re.IGNORECASE,
)

CONVERSATION_RECAP_PATTERN = re.compile(
    r"\b("
    r"what were we (talking|discussing) about( before)?|what did we (talk|discuss)( before)?|"
    r"recap (that |our )?conversation|previous conversation|last conversation|"
    r"earlier in (this )?chat|what have we (talked|discussed)|remind me what we|"
    r"sent a message|message around|recap (that |the )?chat|earlier today|"
    r"conversation from|chat from|"
    r"continue from where we left off|pick up where we left off|where we left off|"
    r"continue (the |our )?conversation|resume (the |our )?conversation"
    r")\b",
    re.IGNORECASE,
)

CROSS_SESSION_PATTERN = re.compile(
    r"\b("
    r"another sessions?|other sessions?|different (chats?|sessions?)|"
    r"previous sessions?|earlier sessions?|other chats?|that sessions?|"
    r"was in another|different conversation|last conversation|"
    r"continue from where we left off|pick up where we left off|where we left off|"
    r"what about (in )?(other|another|previous) (sessions?|chats?)|"
    r"how about (in )?(other|another|previous) (sessions?|chats?)|"
    r"(in|from) (other|another|previous) (sessions?|chats?)"
    r")\b",
    re.IGNORECASE,
)

TIME_HINT_PATTERN = re.compile(
    r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b",
    re.IGNORECASE,
)

REPO_CREATED_PATTERN = re.compile(
    r"\b("
    r"when was (the |this )?repo (created|made)|repo creation|repository created|"
    r"when was (the |this )?project created|date (the )?repo was created"
    r")\b",
    re.IGNORECASE,
)

FILE_CHURN_PATTERN = re.compile(
    r"\b("
    r"most (changed|updated|modified) file|file.*(changed|updated) (the )?most|"
    r"which file.*(changed|updated) most|hotspot|churn|frequently changed"
    r")\b",
    re.IGNORECASE,
)

FILE_HISTORY_PATTERN = re.compile(
    r"\b("
    r"when was .+ introduced|when did .+ change|when was .+ added|"
    r"first commit.*(?:file|touch)|introduced in commit|"
    r"history of (?:the )?file|when was (?:this |the )?(?:function|method|class)|"
    r"when was .+ (?:created|implemented)|file history|trace .+ history"
    r")\b",
    re.IGNORECASE,
)

FILE_PATH_EXTRACT = re.compile(
    r"(?:\b(?:file|path)\s+)?"
    r"((?:[\w.-]+/)+[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|php|cs|md|json|yaml|yml|toml|sql|sh))"
    r"|"
    r"\b([\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|php|cs|md|json|yaml|yml|toml|sql|sh))\b",
    re.IGNORECASE,
)

SYMBOL_EXTRACT = re.compile(
    r"\b(?:function|method|class|def)\s+['\"]?(\w+)['\"]?|"
    r"\b(\w+)\(\)|"
    r"when was (?:the )?(\w+) (?:function|method|class)",
    re.IGNORECASE,
)

STACK_PATTERN = re.compile(
    r"\b("
    r"stack|framework|database|dependencies|functionality|functionalities|"
    r"architect|authentication|auth|api|technology|technologies|"
    r"package\.json|built with|using what|core feature|entry point|"
    r"what does.*do|how does.*work|what is this|tell me about|mongoose|"
    r"express|fastify|nestjs|postgres|mongodb"
    r")\b",
    re.IGNORECASE,
)

PROJECT_NAME_PATTERN = re.compile(
    r"\b("
    r"name of (my |the )?project|project name|what(?:'s| is) (my |the )?project|"
    r"which (repo|repository)|what repo am i|current project"
    r")\b",
    re.IGNORECASE,
)

LAST_COMMIT_AUTHOR_PATTERN = re.compile(
    r"\b(who made the last commits?|who committed last|last commits? author|"
    r"who pushed last|who wrote the last commits?)\b",
    re.IGNORECASE,
)

RECENT_CHANGES_PATTERN = re.compile(
    r"\b(what changed recently|recent changes|latest changes|what's new|"
    r"what happened recently|changes this week)\b",
    re.IGNORECASE,
)

COMMIT_CHANGE_PATTERN = re.compile(
    r"\b("
    r"what did (they|he|she|the person|that person|the author|.*) change|"
    r"what changed in (that|the|this) commit|what was changed|"
    r"show me the (diff|changes)|what files changed|what files (were |)(touched|modified)|"
    r"what did .* commit|what was committ?ed|show.*committ?ed|show.*last commit|"
    r"what.*in the last commit|contents? of (the )?last commit|"
    r"enumerate.*files|walk through.*(change|modif)|modifications? in (that |the |this )?commit|"
    r"break\s*down.*(change|commit|modif)|"
    r"commit [0-9a-f]{7,40}|in commit [0-9a-f]{7,40}|about commit|that commit|this commit"
    r")\b",
    re.IGNORECASE,
)

PREVIOUS_COMMIT_PATTERN = re.compile(
    r"\b("
    r"commit before (this|that|it|the last)|previous commit|prior commit|"
    r"what was (the )?commit before|commit (right )?before (this|that|it)|"
    r"one before (this|that|it)|before (this|that) (one|commit)"
    r")\b",
    re.IGNORECASE,
)

FIRST_COMMIT_PATTERN = re.compile(
    r"\b("
    r"(very )?first commit|initial commit|oldest commit|earliest commit|"
    r"commit at the (start|beginning)|root commit|original commit|"
    r"beginning of (the )?(repo|repository|project) history|"
    r"start of (the )?(repo|repository|project)"
    r")\b",
    re.IGNORECASE,
)

COMMIT_ENDPOINTS_PATTERN = re.compile(
    r"\b("
    r"first (and|&) last commits?|last (and|&) first commits?|"
    r"oldest (and|&) (newest|latest) commits?|"
    r"(newest|latest) (and|&) oldest commits?|"
    r"earliest (and|&) latest commits?|latest (and|&) earliest commits?|"
    r"first (and|&) most recent commits?|most recent (and|&) first commits?"
    r")\b",
    re.IGNORECASE,
)

PARENT_COMMIT_PATTERN = re.compile(
    r"\b("
    r"parent (of |commit (for )?)?|what(?:'s| is) the parent (of |commit )?|"
    r"parents? of (the )?commit|who is the parent"
    r")\b",
    re.IGNORECASE,
)

COMMIT_COMPARE_PATTERN = re.compile(
    r"\b("
    r"compare (both|them|the two|these|the last|last)|compare.*commits?|"
    r"difference(s)? between (both|them|the two|these|commits?|the last|last)|"
    r"check and compare|side.?by.?side|compare between|"
    r"last \d+ commits?|last (two|three|four|five|six|seven) commits?"
    r")\b",
    re.IGNORECASE,
)

RECENT_COMMIT_COUNT_WORDS = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
}

COMMIT_FILE_LIST_PATTERN = re.compile(
    r"\b("
    r"file list|list (of )?(the )?files|files (changed|affected|modified|touched)|"
    r"show (me )?(the )?files|check the file|what files|enumerate.*files|"
    r"files in (that|this|the) commit"
    r")\b",
    re.IGNORECASE,
)

PRONOUN_COMMIT_PATTERN = re.compile(
    r"\b(it|that commit|this commit|the previous one|the other one|that one|this one)\b",
    re.IGNORECASE,
)

SHA_IN_TEXT = re.compile(r"\b([0-9a-f]{7,40})\b", re.IGNORECASE)

KEY_CONFIG_FILES = (
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "docker-compose.yml",
    "Dockerfile",
    "tsconfig.json",
)

SOURCE_ENTRY_CANDIDATES = (
    "src/app.ts",
    "src/index.ts",
    "src/main.ts",
    "src/server.ts",
    "app/main.py",
    "app/main.ts",
    "main.py",
    "index.js",
    "index.ts",
)

EXPLORE_DIRS = ("src", "app", "server", "api", "lib")


def is_project_name_question(message: str) -> bool:
    return bool(PROJECT_NAME_PATTERN.search(message))


def is_last_commit_author_question(message: str) -> bool:
    return bool(LAST_COMMIT_AUTHOR_PATTERN.search(message))


def is_recent_changes_question(message: str) -> bool:
    return bool(RECENT_CHANGES_PATTERN.search(message))


def is_commit_change_question(message: str) -> bool:
    return bool(COMMIT_CHANGE_PATTERN.search(message))


def is_previous_commit_question(message: str) -> bool:
    return bool(PREVIOUS_COMMIT_PATTERN.search(message))


def is_commit_endpoints_question(message: str) -> bool:
    return bool(COMMIT_ENDPOINTS_PATTERN.search(message))


def is_first_commit_question(message: str) -> bool:
    if is_commit_endpoints_question(message):
        return False
    return bool(FIRST_COMMIT_PATTERN.search(message))


def is_parent_commit_question(message: str) -> bool:
    return bool(PARENT_COMMIT_PATTERN.search(message))


def parse_recent_commit_count(message: str) -> int | None:
    """Extract N from phrases like 'last 3 commits' or 'recent five commits'."""
    match = re.search(
        r"\b(?:last|latest|recent)\s+(\d+)\s+commits?\b",
        message,
        re.I,
    )
    if match:
        return min(max(int(match.group(1)), 2), 20)
    match = re.search(
        r"\b(?:last|latest|recent)\s+(two|three|four|five|six|seven)\s+commits?\b",
        message,
        re.I,
    )
    if match:
        return RECENT_COMMIT_COUNT_WORDS.get(match.group(1).lower())
    return None


def is_multi_commit_compare_question(message: str) -> bool:
    return parse_recent_commit_count(message) is not None and is_commit_compare_question(
        message
    )


def is_commit_compare_question(message: str) -> bool:
    return bool(COMMIT_COMPARE_PATTERN.search(message)) or _has_two_shas(message)


def is_commit_file_list_question(message: str) -> bool:
    return bool(COMMIT_FILE_LIST_PATTERN.search(message))


def mentions_commit_sha(message: str) -> bool:
    return bool(SHA_IN_TEXT.search(message))


def _has_two_shas(message: str) -> bool:
    return len(SHA_IN_TEXT.findall(message)) >= 2


def should_fetch_commit_detail(message: str) -> bool:
    """Whether to pull full commit file/diff data from GitHub for this message."""
    return (
        is_commit_change_question(message)
        or is_commit_compare_question(message)
        or is_commit_file_list_question(message)
        or is_previous_commit_question(message)
        or mentions_commit_sha(message)
        or bool(
            re.search(
                r"\b(what did|what was|show|describe|explain|check|inspect).*(change|diff|modify|committ?ed|commit|files?)\b",
                message,
                re.I,
            )
        )
        or bool(PRONOUN_COMMIT_PATTERN.search(message) and re.search(r"\b(file|diff|change|commit)\b", message, re.I))
    )


def is_commit_count_question(message: str) -> bool:
    return bool(COMMIT_COUNT_PATTERN.search(message))


def is_contributor_question(message: str) -> bool:
    return bool(CONTRIBUTOR_PATTERN.search(message))


def needs_repo_stats(message: str) -> bool:
    return is_commit_count_question(message) or is_contributor_question(message)


def is_deployment_question(message: str) -> bool:
    return bool(DEPLOYMENT_PATTERN.search(message))


def is_ci_question(message: str) -> bool:
    return bool(CI_PATTERN.search(message))


def is_release_question(message: str) -> bool:
    return bool(RELEASE_PATTERN.search(message))


def is_activity_overview_question(message: str) -> bool:
    return bool(ACTIVITY_OVERVIEW_PATTERN.search(message))


def needs_repo_activity(message: str) -> bool:
    return (
        is_deployment_question(message)
        or is_ci_question(message)
        or is_release_question(message)
        or is_activity_overview_question(message)
        or is_recent_changes_question(message)
        or needs_commit_history(message)
    )


def is_conversation_recap_question(message: str) -> bool:
    return bool(CONVERSATION_RECAP_PATTERN.search(message))


def is_cross_session_question(message: str) -> bool:
    return bool(CROSS_SESSION_PATTERN.search(message)) or parse_time_hint(message) is not None


def _has_prior_user_messages(history: list[dict[str, str]] | None) -> bool:
    return any(m.get("role") == "user" for m in (history or []))


def _has_substantive_current_session(history: list[dict[str, str]] | None) -> bool:
    """True when this session has real repo/engineering discussion (not just recap meta)."""
    for msg in history or []:
        if msg.get("source") == "intro":
            continue
        content = msg.get("content") or ""
        if msg.get("role") == "user":
            if _is_meta_continuation_message(content):
                continue
            if is_conversation_recap_question(content) or is_cross_session_question(content):
                continue
            return True
        if msg.get("role") == "assistant":
            lower = content.lower()
            if "just started this chat session" in lower:
                continue
            if _RECAP_OUTPUT_PATTERN.search(content):
                continue
            if re.search(
                r"\b(commit|github|repo|files? changed|compare|contributor)\b",
                content,
                re.I,
            ):
                return True
    return False


def implies_other_session(
    message: str, history: list[dict[str, str]] | None = None
) -> bool:
    """Whether to load and use chat sessions other than the current one."""
    if is_cross_session_question(message):
        return True
    if not is_conversation_recap_question(message):
        if _is_other_session_follow_up(message, history):
            return True
        return False
    # "before / previously" → prior session, even if this session already has messages
    if re.search(
        r"\b(before|previously|earlier|last time|other sessions?|another sessions?)\b",
        message,
        re.I,
    ):
        return True
    # No substantive work in this session yet → look at other sessions
    if not _has_substantive_current_session(history):
        return True
    return bool(
        re.search(
            r"\b(last conversation|another sessions?|other sessions?|"
            r"where we left off|continue from|pick up where)\b",
            message,
            re.I,
        )
    )


def should_use_other_sessions(
    message: str,
    history: list[dict[str, str]] | None,
    other_sessions: list[dict] | None = None,
) -> bool:
    """Route to cross-session handling when other chats should be consulted."""
    if not other_sessions:
        return False
    if implies_other_session(message, history):
        return True
    if (
        is_conversation_recap_question(message)
        and not _has_substantive_current_session(history)
    ):
        return True
    return False


def prefers_breakdown_summary(message: str) -> bool:
    """Structured session summary instead of transcript-style replay."""
    if is_continuation_request(message):
        return True
    return bool(
        re.search(r"\b(before|previously|earlier|last time)\b", message, re.I)
    )


def _is_other_session_follow_up(
    message: str, history: list[dict[str, str]] | None
) -> bool:
    """e.g. 'what about in other sessions' after asking what we discussed."""
    if not re.search(
        r"\b(what|how) about\b.*\b(other|another|previous)\b",
        message,
        re.I,
    ) and not re.search(
        r"\b(in|from)\s+(other|another|previous)\s+(sessions?|chats?)\b",
        message,
        re.I,
    ):
        return False
    for msg in reversed(history or []):
        if msg.get("role") != "user":
            continue
        if is_conversation_recap_question(msg.get("content", "")):
            return True
        if is_cross_session_question(msg.get("content", "")):
            return True
        break
    return False


def should_load_other_sessions(
    message: str, history: list[dict[str, str]] | None = None
) -> bool:
    return implies_other_session(message, history)


def parse_time_hint(message: str):
    """Parse a clock time like '10:11 am' from the message."""
    from datetime import time

    match = TIME_HINT_PATTERN.search(message)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = (match.group(3) or "").lower()
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    return time(hour, minute)


def is_explicit_recap_request(message: str) -> bool:
    """User wants a transcript-style recap, not to resume work."""
    return bool(
        re.search(
            r"\b("
            r"recap|what did we (talk|discuss)|what were we (talking|discussing)|"
            r"remind me what we|show me what we (talked|discussed)|"
            r"what happened (in|during) (that|the) (chat|session|conversation)"
            r")\b",
            message,
            re.I,
        )
    )


def is_continuation_request(message: str) -> bool:
    """User wants to resume prior work — not a full session dump."""
    if is_explicit_recap_request(message):
        return False
    return bool(
        re.search(
            r"\b(continue|left off|pick up|resume|carry on|keep going)\b",
            message,
            re.I,
        )
        or re.search(r"\bwhere we left off\b", message, re.I)
    )


_META_CONTINUATION_PATTERN = re.compile(
    r"\b("
    r"continue from where we left off|pick up where we left off|where we left off|"
    r"resume (the |our )?conversation|continue (the |our )?conversation|"
    r"last conversation"
    r")\b",
    re.I,
)

_RECAP_OUTPUT_PATTERN = re.compile(
    r"here'?s what I found in your other chat session",
    re.I,
)


def _is_meta_continuation_message(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return True
    if _RECAP_OUTPUT_PATTERN.search(text):
        return True
    if _META_CONTINUATION_PATTERN.search(text) and len(text) < 200:
        return True
    return False


def _unique_shas_in_text(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for sha in SHA_IN_TEXT.findall(text):
        short = sha[:7].lower()
        if short in seen:
            continue
        seen.add(short)
        ordered.append(sha)
    return ordered


def _session_substance_score(session: dict) -> int:
    score = 0
    title = session.get("title") or ""
    if _META_CONTINUATION_PATTERN.search(title):
        score -= 15
    messages = session.get("messages") or []
    substantive_users = 0
    for msg in messages:
        content = msg.get("content") or ""
        if msg.get("role") == "user":
            if _is_meta_continuation_message(content):
                score -= 4
            else:
                substantive_users += 1
                score += 3
        if _is_meta_continuation_message(content):
            score -= 3
        if SHA_IN_TEXT.search(content):
            score += 2
        if re.search(r"\b(compare|commit|diff|file list|files affected)\b", content, re.I):
            score += 2
    score += min(substantive_users, 5)
    return score


def pick_substantive_session(other_sessions: list[dict]) -> dict | None:
    """Prefer the session with real repo work over meta 'continue' chats."""
    if not other_sessions:
        return None
    ranked = sorted(
        other_sessions,
        key=lambda s: (_session_substance_score(s), s.get("updated_at") or ""),
        reverse=True,
    )
    best = ranked[0]
    if _session_substance_score(best) < 0 and len(ranked) > 1:
        return ranked[1]
    return best


def _pending_work_from_messages(messages: list[dict]) -> list[str]:
    """Infer outstanding tasks from substantive user messages."""
    tasks: list[str] = []
    seen: set[str] = set()
    patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"\bcompare\b.*\bcommit", re.I), "compare the commits you discussed"),
        (re.compile(r"\bcheck and compare\b", re.I), "compare the commits you discussed"),
        (
            re.compile(r"\bfile list\b|\bfiles affected\b|\bcheck the file\b", re.I),
            "review file lists for those commits",
        ),
        (
            re.compile(r"\bcommit before\b|\bparent\b.*\bcommit\b|\bprevious commit\b", re.I),
            "identify parent/previous commits",
        ),
        (re.compile(r"\bhow many commits\b", re.I), "count commits on the branch"),
        (
            re.compile(r"\bbreak\s*down\b|\bwhat (was |)(changed|committed)\b", re.I),
            "break down what changed in a commit",
        ),
    ]
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content") or ""
        if _is_meta_continuation_message(content):
            continue
        for pattern, label in patterns:
            if pattern.search(content) and label not in seen:
                seen.add(label)
                tasks.append(label)
    return list(reversed(tasks))[:4]


def _topics_from_messages(messages: list[dict]) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    patterns: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"\bcompare\b.*\bcommit", re.I), "Commit comparison"),
        (re.compile(r"\bcheck and compare\b", re.I), "Commit comparison"),
        (re.compile(r"\bhow many commits\b", re.I), "Commit count on branch"),
        (re.compile(r"\bfile list\b|\bfiles affected\b", re.I), "Files changed in commits"),
        (re.compile(r"\bcommit before\b|\bprevious commit\b", re.I), "Parent/previous commit"),
        (re.compile(r"\bwho made\b.*\bcommit\b", re.I), "Commit authorship"),
        (re.compile(r"\b(first|initial|oldest) commit\b", re.I), "Repository history"),
        (re.compile(r"\bauthentication\b|\bhow does auth\b", re.I), "Authentication"),
        (re.compile(r"\bwhat changed\b|\bbreak\s*down\b", re.I), "Change analysis"),
        (re.compile(r"\bdeploy(ment)?\b|\bci\b|\bbuild\b", re.I), "CI/CD and deployments"),
    ]
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content") or ""
        if _is_meta_continuation_message(content):
            continue
        for pattern, label in patterns:
            if pattern.search(content) and label not in seen:
                seen.add(label)
                topics.append(label)
    return topics


def _format_session_breakdown(
    session: dict,
    *,
    header: str | None = None,
) -> list[str]:
    """Structured breakdown of a session — topics, commits, pending work."""
    title = session.get("title") or "Untitled"
    when = session.get("time_label") or ""
    messages = session.get("messages") or []
    filtered = [
        m
        for m in messages
        if not _is_meta_continuation_message(m.get("content", ""))
    ]
    all_text = "\n".join(m.get("content", "") for m in filtered)
    shas = _unique_shas_in_text(all_text)
    topics = _topics_from_messages(filtered)
    pending = _pending_work_from_messages(filtered)

    hdr = header or f"Session: \"{title}\""
    lines = [hdr + (f" ({when})" if when else "")]

    if topics:
        lines.append("Topics covered:")
        for topic in topics:
            lines.append(f"  • {topic}")

    if shas:
        lines.append(
            "Commits referenced: " + ", ".join(s[:7] for s in shas[:6])
        )

    if pending:
        lines.append("Where you left off:")
        for task in pending:
            lines.append(f"  • {task.capitalize()}")

    if not topics and not shas and not pending:
        last_user = next(
            (
                m.get("content", "").strip()
                for m in reversed(filtered)
                if m.get("role") == "user"
            ),
            "",
        )
        if last_user:
            snippet = last_user.replace("\n", " ")
            if len(snippet) > 100:
                snippet = snippet[:97] + "..."
            lines.append(f"Last question: \"{snippet}\"")

    return lines


def _history_as_session(history: list[dict[str, str]]) -> dict:
    messages = [
        m
        for m in history
        if m.get("source") != "intro" and (m.get("content") or "").strip()
    ]
    return {"title": "This session", "time_label": "", "messages": messages}


def needs_session_recap(message: str) -> bool:
    return is_conversation_recap_question(message) or is_cross_session_question(message)


def is_repo_created_question(message: str) -> bool:
    return bool(REPO_CREATED_PATTERN.search(message))


def is_file_churn_question(message: str) -> bool:
    return bool(FILE_CHURN_PATTERN.search(message))


def is_file_history_question(message: str) -> bool:
    if is_repo_created_question(message):
        return False
    return bool(FILE_HISTORY_PATTERN.search(message))


def extract_file_path_from_message(message: str) -> str | None:
    match = FILE_PATH_EXTRACT.search(message)
    if not match:
        return None
    return match.group(1) or match.group(2)


def extract_symbol_from_message(message: str) -> str | None:
    match = SYMBOL_EXTRACT.search(message)
    if not match:
        return None
    return match.group(1) or match.group(2) or match.group(3)


def format_file_history_block(trace: dict) -> str:
    if not trace.get("found"):
        path = trace.get("file_path", "the file")
        branch = trace.get("branch", "main")
        analyzed = trace.get("commits_analyzed", 0)
        return (
            f"FILE HISTORY (VERIFIED — Source: GitHub)\n"
            f"No changes to {path} were found in the last {analyzed} commits "
            f"on {branch}. The file may be older than the analyzed window or "
            f"may not exist on this branch."
        )

    lines = [
        "FILE HISTORY (VERIFIED — Source: GitHub)",
        f"File: {trace.get('file_path')}",
        f"Branch: {trace.get('branch', 'main')}",
        f"Commits analyzed: {trace.get('commits_analyzed', 0)}",
        "",
    ]

    intro = trace.get("introduction") or {}
    if intro:
        lines.extend([
            "Introduction (first touch in analyzed history):",
            f"• Commit: {intro.get('short_sha')} ({intro.get('sha', '')})",
            f"• Status: {intro.get('status')}",
            f"• Author: {intro.get('author')}",
            f"• Date: {intro.get('date')}",
            f"• Message: {intro.get('message')}",
            "",
        ])

    last = trace.get("last_change") or {}
    if last and last.get("sha") != intro.get("sha"):
        lines.extend([
            "Most recent change in analyzed history:",
            f"• Commit: {last.get('short_sha')}",
            f"• Status: {last.get('status')}",
            f"• Author: {last.get('author')}",
            f"• Date: {last.get('date')}",
            "",
        ])

    sym = trace.get("symbol_introduction")
    if trace.get("symbol"):
        if sym:
            lines.extend([
                f"Symbol '{trace['symbol']}' first seen in diff:",
                f"• Commit: {sym.get('short_sha')}",
                f"• Date: {sym.get('date')}",
                f"• Message: {sym.get('message')}",
            ])
        else:
            lines.append(
                f"Symbol '{trace['symbol']}' was not found in commit diffs for this "
                f"file within the analyzed history. It may predate the window or "
                f"exist without line-level diff evidence."
            )

    return "\n".join(lines)


def answer_file_history(trace: dict) -> str:
    if not trace.get("found"):
        path = trace.get("file_path", "that file")
        branch = trace.get("branch", "main")
        analyzed = trace.get("commits_analyzed", 0)
        return (
            f"I analyzed the last {analyzed} commits on {branch} and could not find "
            f"changes to {path}.\n\n"
            f"The file may be outside the analyzed window, on another branch, or not "
            f"yet present in the repository history I retrieved from GitHub."
        )

    intro = trace.get("introduction") or {}
    path = trace.get("file_path", "the file")
    branch = trace.get("branch", "main")
    status = intro.get("status", "modified")

    lines = [
        f"Based on GitHub history for {branch}, {path} was first touched in the "
        f"analyzed window in commit {intro.get('short_sha')} ({status}).",
        "",
        f"Author: {intro.get('author', 'unknown')}",
        f"Date: {intro.get('date', '')}",
        f"Message: {intro.get('message', '')}",
    ]

    sym = trace.get("symbol_introduction")
    if trace.get("symbol"):
        if sym:
            lines.extend([
                "",
                f"The symbol '{trace['symbol']}' first appears in the diff for this "
                f"file in commit {sym.get('short_sha')} on {sym.get('date', '')}.",
            ])
        else:
            lines.extend([
                "",
                f"I could not locate '{trace['symbol']}' in line-level diffs for "
                f"{path} within the analyzed commit window.",
            ])

    last = trace.get("last_change") or {}
    if last.get("sha") and last.get("sha") != intro.get("sha"):
        lines.extend([
            "",
            f"Most recent change in the analyzed history: commit {last.get('short_sha')} "
            f"({last.get('status')}) on {last.get('date', '')}.",
        ])

    lines.append(
        f"\nAnalyzed {trace.get('commits_analyzed', 0)} commits on {branch} "
        f"(verified from GitHub)."
    )
    return "\n".join(lines)


async def fetch_file_history_context(
    access_token: str,
    project: Project,
    message: str,
) -> dict:
    from app.services.evidence import evidence_ref, github_commit_url, github_file_url
    from app.services.github import trace_file_history

    branch = project.default_branch or "main"
    file_path = extract_file_path_from_message(message)
    symbol = extract_symbol_from_message(message)

    if not file_path and symbol:
        file_path = symbol  # best-effort; tracing may still fail without a real path

    if not file_path:
        return {
            "found": False,
            "file_path": None,
            "branch": branch,
            "commits_analyzed": 0,
            "formatted": "No file path could be extracted from the question.",
            "evidence": [],
        }

    trace = await trace_file_history(
        access_token,
        project.repo_full_name,
        file_path,
        branch=branch,
        symbol=symbol,
    )
    refs = []
    intro = trace.get("introduction") or {}
    if intro.get("sha"):
        sha = intro["sha"]
        refs.append(
            evidence_ref(
                f"Introduction commit {intro.get('short_sha')}",
                url=github_commit_url(project.repo_full_name, sha),
                kind="history",
            )
        )
        refs.append(
            evidence_ref(
                trace["file_path"],
                url=github_file_url(project.repo_full_name, sha, trace["file_path"]),
                kind="file",
            )
        )

    return {
        **trace,
        "formatted": format_file_history_block(trace),
        "evidence": refs,
    }


def answer_conversation_recap(history: list[dict[str, str]]) -> str:
    """Summarize this chat session — structured breakdown, not transcript replay."""
    if not _has_substantive_current_session(history):
        return (
            "This chat session doesn't have engineering discussion yet — "
            "only setup or recap messages so far.\n\n"
            "If you were working in an earlier chat, ask about other sessions "
            "or open that session from the sidebar."
        )

    lines = ["Summary of this chat session:\n"]
    lines.extend(_format_session_breakdown(_history_as_session(history), header="Current session"))
    return "\n".join(lines)


def answer_cross_session_recap(
    current_history: list[dict[str, str]],
    other_sessions: list[dict],
    *,
    time_hint_label: str | None = None,
) -> str:
    """Summarize other chat sessions — structured breakdown per session."""
    if not other_sessions:
        hint = f" around {time_hint_label}" if time_hint_label else ""
        return (
            f"I couldn't find another chat session{hint} with messages to recap.\n\n"
            + answer_conversation_recap(current_history)
            + "\n\nCheck the chat sidebar for earlier sessions."
        )

    ranked = sorted(
        other_sessions,
        key=lambda s: (_session_substance_score(s), s.get("updated_at") or ""),
        reverse=True,
    )
    lines = ["Here's what you were working on in other sessions:\n"]
    for sess in ranked[:2]:
        lines.extend(_format_session_breakdown(sess))
        lines.append("")

    lines.append(
        "Say \"let's continue\" to pick up where you left off — "
        "I'll pull fresh data from GitHub for any follow-up."
    )
    return "\n".join(lines).strip()


def answer_cross_session_continuation(
    other_sessions: list[dict],
    *,
    repo_name: str | None = None,
) -> str:
    """Concise continuation — structured breakdown of prior work."""
    if not other_sessions:
        return (
            "I couldn't find a prior chat session to continue from. "
            "Open an earlier chat from the sidebar, or tell me what you'd like to work on."
        )

    sess = pick_substantive_session(other_sessions) or other_sessions[0]
    repo = repo_name or "your repository"
    lines = [
        f"Picking up from your {repo} work:\n",
    ]
    lines.extend(_format_session_breakdown(sess))
    lines.append(
        "\nI can pull fresh commit data from GitHub — compare commits, file lists, "
        "diffs, or parent commits. What should we do next?"
    )
    return "\n".join(lines)


def answer_repo_created(repo_meta: dict, repo_name: str) -> str:
    created = repo_meta.get("created_at")
    pushed = repo_meta.get("pushed_at")
    if not created:
        return f"I couldn't retrieve the creation date for {repo_name} from GitHub."

    lines = [
        f"The GitHub repository {repo_name} was created on {created}.",
    ]
    if pushed:
        lines.append(f"Last push to the repository: {pushed}.")
    if repo_meta.get("html_url"):
        lines.append(f"Repository URL: {repo_meta['html_url']}")
    return "\n".join(lines)


def answer_file_churn(churn: dict, repo_name: str) -> str:
    analyzed = churn.get("commits_analyzed", 0)
    if not analyzed:
        return f"I couldn't find commits to analyze in {repo_name}."

    by_commits = churn.get("by_commit_count") or []
    by_lines = churn.get("by_line_changes") or []

    lines = [
        f"I analyzed {analyzed} commits on {repo_name}.\n",
        "Files touched in the most commits:",
    ]
    for filename, count in by_commits[:10]:
        lines.append(f"• {filename} — changed in {count} commits")

    if by_lines:
        lines.append("\nFiles with the most line changes (additions + deletions):")
        for filename, total in by_lines[:10]:
            lines.append(f"• {filename} — {total:,} lines changed")

    return "\n".join(lines)


def format_file_churn_block(churn: dict) -> str:
    if not churn.get("commits_analyzed"):
        return "No file churn data available."
    lines = [f"Commits analyzed: {churn['commits_analyzed']}"]
    for filename, count in (churn.get("by_commit_count") or [])[:10]:
        lines.append(f"• {filename}: {count} commits")
    return "\n".join(lines)


def _sha_from_history(history: list[dict[str, str]] | None) -> str | None:
    for msg in reversed(history or []):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        for pattern in (
            r"Commit:\s*([0-9a-f]{7,40})",
            r"Commit hash:\s*([0-9a-f]{7,40})",
            r"hash:\s*([0-9a-f]{7,40})",
        ):
            match = re.search(pattern, content, re.I)
            if match:
                return match.group(1)
    return None


def _last_mentioned_sha(
    history: list[dict[str, str]] | None,
    *,
    exclude_prefix: str | None = None,
) -> str | None:
    for msg in reversed(history or []):
        matches = list(SHA_IN_TEXT.finditer(msg.get("content", "")))
        if not matches:
            continue
        sha = matches[-1].group(1)
        if exclude_prefix and sha.lower().startswith(exclude_prefix.lower()[:7]):
            continue
        return sha
    return None


def _refers_to_previous_commit(message: str) -> bool:
    return bool(
        re.search(
            r"\b(the previous one|previous commit|that one|the other one|"
            r"commit before|before (this|that|the last|it)|prior commit)\b",
            message,
            re.I,
        )
    )


def resolve_commit_targets(
    message: str,
    history: list[dict[str, str]] | None = None,
    *,
    stored_sha: str | None = None,
    stored_previous_sha: str | None = None,
) -> dict:
    """Resolve which commit SHAs a message refers to."""
    explicit = SHA_IN_TEXT.findall(message)
    recent_n = parse_recent_commit_count(message)

    if recent_n and is_commit_compare_question(message):
        return {
            "intent": "multi_compare",
            "count": recent_n,
            "shas": explicit[:recent_n] if explicit else [],
            "primary": stored_sha,
            "secondary": stored_previous_sha,
        }

    if len(explicit) >= 2:
        intent = "multi_compare" if len(explicit) >= 3 else "compare"
        return {
            "intent": intent,
            "count": len(explicit),
            "shas": explicit,
            "primary": explicit[0],
            "secondary": explicit[1] if len(explicit) > 1 else None,
        }

    if explicit:
        return {"intent": "single", "shas": [explicit[0]], "primary": explicit[0], "secondary": None}

    if is_commit_compare_question(message):
        if stored_sha and stored_previous_sha and not recent_n:
            return {
                "intent": "compare",
                "count": 2,
                "shas": [stored_sha, stored_previous_sha],
                "primary": stored_sha,
                "secondary": stored_previous_sha,
            }
        shas = _conversation_shas(history)
        if len(shas) >= 2 and not recent_n:
            intent = "multi_compare" if len(shas) >= 3 else "compare"
            return {
                "intent": intent,
                "count": len(shas),
                "shas": shas,
                "primary": shas[0],
                "secondary": shas[1],
            }

    if is_previous_commit_question(message):
        return {
            "intent": "previous",
            "shas": [stored_sha] if stored_sha else [],
            "primary": stored_sha,
            "secondary": None,
        }

    if _refers_to_previous_commit(message) or (
        PRONOUN_COMMIT_PATTERN.search(message)
        and stored_previous_sha
        and _conversation_mentions_previous(history)
    ):
        if stored_previous_sha:
            return {
                "intent": "single",
                "shas": [stored_previous_sha],
                "primary": stored_previous_sha,
                "secondary": None,
            }
        alt = _last_mentioned_sha(history, exclude_prefix=stored_sha)
        if alt:
            return {"intent": "single", "shas": [alt], "primary": alt, "secondary": None}

    if PRONOUN_COMMIT_PATTERN.search(message):
        alt = _last_mentioned_sha(history, exclude_prefix=stored_sha) or stored_previous_sha
        if alt and alt != stored_sha:
            return {"intent": "single", "shas": [alt], "primary": alt, "secondary": None}

    if stored_sha:
        return {"intent": "single", "shas": [stored_sha], "primary": stored_sha, "secondary": None}

    history_sha = _sha_from_history(history) or _last_mentioned_sha(history)
    if history_sha:
        return {"intent": "single", "shas": [history_sha], "primary": history_sha, "secondary": None}

    return {"intent": None, "shas": [], "primary": None, "secondary": None}


def _conversation_shas(history: list[dict[str, str]] | None) -> list[str]:
    seen: list[str] = []
    for msg in history or []:
        for match in SHA_IN_TEXT.finditer(msg.get("content", "")):
            sha = match.group(1)
            if sha not in seen:
                seen.append(sha)
    return seen


def _conversation_mentions_previous(history: list[dict[str, str]] | None) -> bool:
    recent = list(reversed(history or []))[:4]
    for msg in recent:
        if re.search(
            r"\b(previous commit|commit before|before (this|that|the last|it)|prior commit)\b",
            msg.get("content", ""),
            re.I,
        ):
            return True
    return False


def extract_commit_sha(
    message: str,
    history: list[dict[str, str]] | None = None,
    stored_sha: str | None = None,
    stored_previous_sha: str | None = None,
) -> str | None:
    targets = resolve_commit_targets(
        message,
        history,
        stored_sha=stored_sha,
        stored_previous_sha=stored_previous_sha,
    )
    return targets.get("primary")


def get_latest_commit_sha(ctx: dict) -> str | None:
    commits = ctx.get("commits") or []
    if not commits:
        return None
    latest = commits[0]
    return latest.get("sha") or str(latest.get("id", ""))


def get_previous_commit_sha(ctx: dict, current_sha: str | None = None) -> str | None:
    commits = ctx.get("commits") or []
    if not commits:
        return None
    if not current_sha:
        if len(commits) < 2:
            return None
        return commits[1].get("sha") or str(commits[1].get("id", ""))
    prefix = current_sha[:7].lower()
    for idx, commit in enumerate(commits):
        sha = commit.get("sha") or str(commit.get("id", ""))
        if sha.lower().startswith(prefix) and idx + 1 < len(commits):
            prev = commits[idx + 1]
            return prev.get("sha") or str(prev.get("id", ""))
    return None


def answer_previous_commit(ctx: dict, current_sha: str | None) -> tuple[str, str | None]:
    repo = ctx.get("repo", "the repository")
    branch = ctx.get("branch", "main")
    commits = ctx.get("commits") or []
    if not commits:
        return f"I couldn't find commit history for {repo}.", None

    current = current_sha or get_latest_commit_sha(ctx)
    previous_sha = get_previous_commit_sha(ctx, current)
    if not previous_sha:
        short = (current or "")[:7]
        return (
            f"On the {branch} branch, I found commit {short} but couldn't identify "
            "the commit immediately before it in the recent history."
        ), None

    previous = next(
        (c for c in commits if (c.get("sha") or "").startswith(previous_sha[:7])),
        commits[1] if len(commits) > 1 else {},
    )
    short_prev = previous_sha[:7]
    return (
        f"On the {branch} branch, the commit before "
        f"{(current or '')[:7]} is:\n\n"
        f"Commit: {short_prev}\n"
        f"Message: {previous.get('title', '')}\n"
        f"Author: {previous.get('author', 'unknown')}\n"
        f"Date: {previous.get('date') or previous.get('time', '')}"
    ), previous_sha


def format_commit_detail_block(detail: dict) -> str:
    lines = [
        f"Commit: {detail.get('short_sha') or detail.get('sha', '')[:7]}",
        f"Author: {detail.get('author')}",
        f"Date: {detail.get('date')}",
        f"Message: {detail.get('title')}",
    ]
    if detail.get("additions") or detail.get("deletions"):
        lines.append(
            f"Stats: +{detail.get('additions', 0)} / -{detail.get('deletions', 0)}"
        )

    files = detail.get("files") or []
    if files:
        lines.append("\nFiles changed:")
        for f in files:
            lines.append(
                f"• {f.get('filename')} ({f.get('status', 'modified')}, "
                f"+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
            )

    if detail.get("diff_excerpt"):
        lines.append(f"\nCommit diff:\n{detail['diff_excerpt']}")
    elif not detail.get("has_diff"):
        lines.append(
            "\nNote: Commit diff is not available from GitHub for this commit."
        )

    return "\n".join(lines)


def commit_evidence_sources(detail: dict) -> list[str]:
    sources = [f"Commit {detail.get('short_sha') or detail.get('sha', '')[:7]}"]
    file_count = detail.get("file_count")
    if file_count is None:
        file_count = len(detail.get("files") or [])
    if file_count:
        sources.append(f"{file_count} files changed")
    for f in (detail.get("files") or [])[:6]:
        sources.append(f.get("filename", ""))
    if detail.get("has_diff"):
        sources.append("Commit diff")
    return [s for s in sources if s]


def answer_commit_file_list(
    detail: dict,
    *,
    branch: str | None = None,
    preamble: str | None = None,
) -> str:
    short = detail.get("short_sha") or detail.get("sha", "")[:7]
    file_count = detail.get("file_count") or len(detail.get("files") or [])
    branch_line = f" (branch: {branch})" if branch else ""
    lines: list[str] = []
    if preamble:
        lines.extend([preamble, ""])
    lines.extend([
        f"Commit {short}{branch_line} changed {file_count} file{'s' if file_count != 1 else ''}:",
        f"Message: {detail.get('title', '')}",
        "",
    ])
    for f in detail.get("files") or []:
        lines.append(
            f"• {f.get('filename')} ({f.get('status', 'modified')}, "
            f"+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
        )
    if not detail.get("files"):
        lines.append("GitHub did not return a changed-file list for this commit.")
    return "\n".join(lines)


async def fetch_recent_commit_shas(
    access_token: str,
    project: Project,
    count: int,
) -> list[str]:
    """Retrieve the N most recent commits on the project branch from GitHub."""
    from app.services.github import list_commits

    branch = project.default_branch or "main"
    commits = await list_commits(
        access_token,
        project.repo_full_name,
        branch=branch,
        per_page=min(max(count, 2), 20),
    )
    return [c.get("sha") or str(c.get("id", "")) for c in commits[:count]]


async def fetch_multi_compare_context(
    access_token: str,
    project: Project,
    shas: list[str],
) -> dict:
    from app.services.commit_compare import (
        compare_multiple_commits,
        format_multi_commit_compare_block,
    )
    from app.services.commit_cache import fetch_commit_details_cached
    from app.services.evidence import multi_compare_evidence_refs

    details = await fetch_commit_details_cached(
        access_token,
        project.repo_full_name,
        shas,
    )
    comparison = compare_multiple_commits(details)
    formatted = format_multi_commit_compare_block(details, comparison)
    refs = multi_compare_evidence_refs(details, comparison, project.repo_full_name)
    return {
        "commits": details,
        "comparison": comparison,
        "formatted": formatted,
        "evidence_sources": [r["label"] for r in refs if r.get("label")],
        "evidence": refs,
    }


async def fetch_compare_context(
    access_token: str,
    project: Project,
    sha_a: str,
    sha_b: str,
) -> dict:
    import asyncio

    from app.services.evidence import compare_evidence_refs

    detail_a, detail_b = await asyncio.gather(
        fetch_commit_context(access_token, project, sha_a),
        fetch_commit_context(access_token, project, sha_b),
    )
    commit_a = detail_a["commit"]
    commit_b = detail_b["commit"]
    comparison = compare_commits(commit_a, commit_b)
    refs = compare_evidence_refs(
        commit_a, commit_b, comparison, project.repo_full_name
    )
    return {
        "commit_a": commit_a,
        "commit_b": commit_b,
        "comparison": comparison,
        "formatted": format_commit_compare_block(commit_a, commit_b),
        "evidence_sources": [r["label"] for r in refs if r.get("label")],
        "evidence": refs,
    }


async def fetch_commit_context(
    access_token: str,
    project: Project,
    sha: str,
) -> dict:
    from app.services.commit_cache import fetch_commit_details_cached
    from app.services.evidence import commit_evidence_refs

    details = await fetch_commit_details_cached(
        access_token,
        project.repo_full_name,
        [sha],
    )
    detail = details[0] if details else {}
    refs = commit_evidence_refs(detail, project.repo_full_name)
    return {
        "repo": project.repo_full_name,
        "commit": detail,
        "formatted": format_commit_detail_block(detail),
        "evidence_sources": [r["label"] for r in refs if r.get("label")],
        "evidence": refs,
    }


async def fetch_commit_endpoints_context(
    access_token: str,
    project: Project,
) -> dict:
    """Retrieve the oldest and newest commits on the project branch."""
    import asyncio

    from app.services.evidence import last_commit_author_evidence

    first_ctx, repo_ctx = await asyncio.gather(
        fetch_first_commit_context(access_token, project),
        gather_chat_context(access_token, project, ""),
    )
    latest = (repo_ctx.get("commits") or [None])[0]
    branch = first_ctx.get("branch", project.default_branch or "main")
    evidence = list(first_ctx.get("evidence") or [])
    if latest:
        latest_sha = latest.get("sha") or latest.get("id")
        evidence.extend(
            last_commit_author_evidence(latest_sha, branch, project.repo_full_name)
        )
    return {
        "repo": project.repo_full_name,
        "branch": branch,
        "first": first_ctx["commit"],
        "latest": latest,
        "total_commits": first_ctx.get("total_commits"),
        "formatted": format_commit_endpoints_block(
            first_ctx["commit"],
            latest,
            branch=branch,
            total_commits=first_ctx.get("total_commits"),
        ),
        "evidence": evidence,
    }


async def fetch_first_commit_context(
    access_token: str,
    project: Project,
) -> dict:
    """Retrieve the oldest commit on the project branch from GitHub."""
    import asyncio

    from app.services.evidence import commit_evidence_refs, evidence_ref
    from app.services.github import count_commits, get_commit_detail, get_oldest_commit_on_branch

    branch = project.default_branch or "main"
    oldest_summary, total_commits = await asyncio.gather(
        get_oldest_commit_on_branch(access_token, project.repo_full_name, branch=branch),
        count_commits(access_token, project.repo_full_name, branch=branch),
    )
    if not oldest_summary:
        raise ValueError(f"No commits found on branch {branch}")

    sha = oldest_summary["sha"]
    detail = await get_commit_detail(access_token, project.repo_full_name, sha)
    refs = commit_evidence_refs(detail, project.repo_full_name)
    refs.insert(
        0,
        evidence_ref(
            f"First commit on {branch}",
            url=oldest_summary.get("html_url"),
            kind="history",
        ),
    )
    return {
        "repo": project.repo_full_name,
        "branch": branch,
        "commit": detail,
        "summary": oldest_summary,
        "total_commits": total_commits,
        "formatted": format_first_commit_block(detail, branch=branch, total_commits=total_commits),
        "evidence": refs,
    }


def format_first_commit_block(
    detail: dict, *, branch: str, total_commits: int | None = None
) -> str:
    short = detail.get("short_sha") or detail.get("sha", "")[:7]
    file_count = detail.get("file_count") or len(detail.get("files") or [])
    lines = [
        f"FIRST COMMIT ON {branch.upper()} (VERIFIED — Source: GitHub)",
        "",
        f"Commit: {short}",
        f"Full SHA: {detail.get('sha', '')}",
        f"Author: {detail.get('author')}",
        f"Date: {detail.get('date')}",
        f"Message: {detail.get('title')}",
        f"Files changed: {file_count}",
    ]
    if total_commits is not None:
        lines.append(f"Total commits on {branch}: {total_commits}")
    parents = detail.get("parent_shas") or []
    if parents:
        lines.append(f"Parent SHAs: {', '.join(p[:7] for p in parents)}")
    else:
        lines.append("Parent SHAs: none (root commit on this branch)")

    files = detail.get("files") or []
    if files:
        lines.append("\nFiles changed:")
        for f in files:
            lines.append(
                f"• {f.get('filename')} ({f.get('status', 'modified')}, "
                f"+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
            )
    elif file_count:
        for path in (detail.get("all_filenames") or [])[:50]:
            lines.append(f"• {path}")

    if detail.get("diff_excerpt"):
        lines.append(f"\nCommit diff:\n{detail['diff_excerpt'][:6000]}")
    elif not detail.get("has_diff"):
        lines.append(
            "\nNote: Line-level diff not available from GitHub for this commit."
        )
    return "\n".join(lines)


def format_commit_endpoints_block(
    first_detail: dict,
    latest_commit: dict | None,
    *,
    branch: str,
    total_commits: int | None = None,
) -> str:
    first_short = first_detail.get("short_sha") or first_detail.get("sha", "")[:7]
    lines = [
        f"COMMIT ENDPOINTS ON {branch.upper()} (VERIFIED — Source: GitHub)",
        "",
        "FIRST COMMIT (oldest on branch):",
        f"Commit: {first_short}",
        f"Full SHA: {first_detail.get('sha', '')}",
        f"Author: {first_detail.get('author')}",
        f"Date: {first_detail.get('date')}",
        f"Message: {first_detail.get('title')}",
    ]
    if latest_commit:
        latest_sha = latest_commit.get("sha") or latest_commit.get("id", "")
        latest_short = latest_sha[:7] if latest_sha else ""
        lines.extend(
            [
                "",
                "LATEST COMMIT (most recent on branch):",
                f"Commit: {latest_short}",
                f"Full SHA: {latest_sha}",
                f"Author: {latest_commit.get('author')}",
                f"Date: {latest_commit.get('date') or latest_commit.get('time', '')}",
                f"Message: {latest_commit.get('title', '')}",
            ]
        )
    else:
        lines.extend(["", "LATEST COMMIT: not available from GitHub."])
    if total_commits is not None:
        lines.extend(["", f"Total commits on {branch}: {total_commits}"])
    return "\n".join(lines)


def answer_commit_endpoints_without_llm(
    first_detail: dict,
    latest_commit: dict | None,
    *,
    branch: str,
    total_commits: int | None = None,
) -> str:
    first_short = first_detail.get("short_sha") or first_detail.get("sha", "")[:7]
    lines = [
        f"Commit endpoints on {branch} (verified from GitHub):",
        "",
        "First commit (oldest on branch):",
        f"• Commit: {first_short}",
        f"• Author: {first_detail.get('author')}",
        f"• Date: {first_detail.get('date')}",
        f"• Message: {first_detail.get('title')}",
    ]
    if latest_commit:
        latest_sha = latest_commit.get("sha") or latest_commit.get("id", "")
        latest_short = latest_sha[:7] if latest_sha else ""
        lines.extend(
            [
                "",
                "Latest commit (most recent on branch):",
                f"• Commit: {latest_short}",
                f"• Author: {latest_commit.get('author')}",
                f"• Date: {latest_commit.get('date') or latest_commit.get('time', '')}",
                f"• Message: {latest_commit.get('title', '')}",
            ]
        )
    else:
        lines.append("")
        lines.append("Latest commit: could not be retrieved from GitHub.")
    if total_commits is not None:
        lines.append(f"\nTotal commits on {branch}: {total_commits}")
    return "\n".join(lines)


def answer_first_commit_without_llm(
    detail: dict, *, branch: str, total_commits: int | None = None
) -> str:
    short = detail.get("short_sha") or detail.get("sha", "")[:7]
    file_count = detail.get("file_count") or len(detail.get("files") or [])
    lines = [
        f"The first commit on {branch} (verified from GitHub):",
        "",
        f"Commit: {short}",
        f"Author: {detail.get('author')}",
        f"Date: {detail.get('date')}",
        f"Message: {detail.get('title')}",
        f"Files changed: {file_count}",
    ]
    if total_commits is not None:
        lines.append(f"Total commits on {branch}: {total_commits}")

    files = detail.get("files") or detail.get("all_filenames") or []
    if files:
        lines.append("")
        lines.append("Files in this commit:")
        for f in files[:25]:
            if isinstance(f, dict):
                lines.append(f"• {f.get('filename')}")
            else:
                lines.append(f"• {f}")
        if len(files) > 25:
            lines.append(f"• … and {len(files) - 25} more")

    parents = detail.get("parent_shas") or []
    if not parents:
        lines.append("")
        lines.append(
            "This commit has no parent in Git metadata — it is the root of this branch history."
        )
    return "\n".join(lines)


def answer_parent_commit(detail: dict, *, branch: str) -> str:
    short = detail.get("short_sha") or detail.get("sha", "")[:7]
    parents = detail.get("parent_shas") or []
    if not parents:
        return (
            f"Commit {short} has no parent commits in Git metadata "
            f"(verified from GitHub). It is likely the root commit on {branch}."
        )
    lines = [
        f"Parent commit(s) of {short} (verified from GitHub):",
        "",
    ]
    for parent in parents:
        lines.append(f"• {parent[:7]} ({parent})")
    return "\n".join(lines)


def find_commit_count_discrepancy(
    history: list[dict[str, str]],
    detail: dict,
) -> str | None:
    """Detect when a prior assistant message reported a different file count for this SHA."""
    sha = (detail.get("short_sha") or detail.get("sha", ""))[:7].lower()
    authoritative = detail.get("file_count")
    if not sha or authoritative is None:
        return None

    patterns = [
        re.compile(
            rf"\b{re.escape(sha)}\b[^\n]{{0,120}}?\b(\d+)\s+(?:files?|items?)\b",
            re.I,
        ),
        re.compile(
            rf"\b(\d+)\s+(?:files?|items?)\b[^\n]{{0,120}}?\b{re.escape(sha)}\b",
            re.I,
        ),
        re.compile(
            rf"changed\s+(\d+)\s+files?[^\n]{{0,80}}?\b{re.escape(sha)}\b",
            re.I,
        ),
    ]

    for msg in history:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content") or ""
        if sha not in content.lower():
            continue
        for pattern in patterns:
            match = pattern.search(content)
            if match:
                prior = int(match.group(1))
                if prior != authoritative:
                    return (
                        f"DISCREPANCY NOTE: Earlier in this conversation, {prior} files were "
                        f"reported for commit {sha}. Authoritative GitHub data reports "
                        f"{authoritative} changed files. Prefer the authoritative count and "
                        f"acknowledge the correction if the user asks about the difference."
                    )
    return None


def answer_commit_changes_without_llm(detail: dict, memory_block: str) -> str:
    parts = [
        "Latest commit",
        f"Author: {detail.get('author')}",
        f"Commit: {detail.get('short_sha') or detail.get('sha', '')[:7]}",
        f"Date: {detail.get('date')}",
        f"Message: {detail.get('title')}",
        "",
    ]

    files = detail.get("files") or []
    if files:
        parts.append("Files changed:")
        for f in files:
            parts.append(
                f"• {f.get('filename')} ({f.get('status', 'modified')}, "
                f"+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
            )
        parts.append("")

    if detail.get("has_diff"):
        parts.append("Diff excerpt:")
        parts.append(detail.get("diff_excerpt", "")[:4000])
    elif files:
        parts.append(
            "GitHub provided the file list above but no line-level diff "
            "(common for very large commits or binary-only changes)."
        )
    else:
        parts.append(
            "Based on the commit message, this commit appears to focus on: "
            f"\"{detail.get('title')}\".\n\n"
            "I could not retrieve file changes from GitHub for this commit."
        )

    if memory_block and "No relevant" not in memory_block:
        parts.append(f"\nRelated project memory:\n{memory_block}")

    return "\n".join(parts)


async def gather_repo_stats(
    access_token: str,
    project: Project,
) -> dict:
    """Fetch aggregate repository statistics from GitHub."""
    full_name = project.repo_full_name
    branch = project.default_branch or "main"
    repo = await get_repo(access_token, full_name)

    commit_count, contributors = await _gather_stats_parallel(
        access_token, full_name, branch
    )

    return {
        "repo": full_name,
        "branch": branch,
        "commit_count": commit_count,
        "contributor_count": len(contributors),
        "contributors": contributors,
        "repo_meta": repo,
    }


async def _gather_stats_parallel(
    access_token: str, full_name: str, branch: str
) -> tuple[int, list[dict]]:
    import asyncio

    commit_count, contributors = await asyncio.gather(
        count_commits(access_token, full_name, branch=branch),
        list_contributors(access_token, full_name),
    )
    return commit_count, contributors


def format_repo_stats_block(stats: dict) -> str:
    lines = [
        f"Repository: {stats['repo']}",
        f"Default branch: {stats['branch']}",
        f"Total commits on {stats['branch']}: {stats['commit_count']}",
        f"Total contributors: {stats['contributor_count']}",
    ]

    repo_meta = stats.get("repo_meta") or {}
    if repo_meta.get("description"):
        lines.append(f"Description: {repo_meta['description']}")
    if repo_meta.get("primary_language") or repo_meta.get("language"):
        lines.append(f"Primary language: {repo_meta.get('language')}")
    if repo_meta.get("created_at"):
        lines.append(f"Created: {repo_meta['created_at']}")
    if repo_meta.get("pushed_at"):
        lines.append(f"Last pushed: {repo_meta['pushed_at']}")

    contributors = stats.get("contributors") or []
    if contributors:
        lines.append("\nTop contributors (by commit count on GitHub):")
        for c in contributors[:15]:
            lines.append(f"• {c['login']}: {c['contributions']} commits")
        if len(contributors) > 15:
            lines.append(f"• … and {len(contributors) - 15} more")

    return "\n".join(lines)


def repo_stats_evidence(stats: dict) -> list[str]:
    evidence = [
        f"{stats['commit_count']} commits on {stats['branch']}",
        f"{stats['contributor_count']} contributors",
        "GitHub contributors API",
    ]
    for c in (stats.get("contributors") or [])[:4]:
        evidence.append(f"{c['login']} ({c['contributions']} commits)")
    return evidence


def answer_commit_count(stats: dict) -> str:
    repo = stats["repo"]
    branch = stats["branch"]
    count = stats["commit_count"]
    return (
        f"The repository {repo} has {count:,} commits on the {branch} branch.\n\n"
        f"This count comes directly from GitHub's commit history for that branch."
    )


def answer_contributor_count(stats: dict) -> str:
    repo = stats["repo"]
    branch = stats.get("branch", "main")
    count = stats["contributor_count"]
    branch_commits = stats.get("commit_count")
    contributors = stats.get("contributors") or []

    lines = [
        f"{count} distinct {'person has' if count == 1 else 'people have'} "
        f"contributed to {repo} (repository-wide), according to GitHub's "
        f"contributors API.",
    ]
    if branch_commits is not None:
        lines.append(
            f"This is separate from the {branch_commits:,} commits currently on "
            f"the {branch} branch — branch history and repo-wide contributor "
            f"counts are not the same thing."
        )
    lines.append("")

    if contributors:
        lines.append("Contributors:")
        for c in contributors[:20]:
            lines.append(f"• {c['login']} — {c['contributions']} commits")
        if len(contributors) > 20:
            lines.append(f"• … and {len(contributors) - 20} more")

    return "\n".join(lines)


def answer_deployments(activity: dict, repo: str) -> str:
    deployments = activity.get("deployments") or []
    if not deployments:
        return f"No deployments are recorded on GitHub for {repo}."

    lines = [f"Recent deployments for {repo}:\n"]
    lines.append(format_deployments_block(deployments))
    envs = activity.get("environments") or []
    if envs:
        lines.append(
            "\nConfigured environments: "
            + ", ".join(e["name"] for e in envs)
        )
    return "\n".join(lines)


def answer_ci_status(activity: dict, repo: str) -> str:
    runs = activity.get("workflow_runs") or []
    if not runs:
        return f"No GitHub Actions workflow runs found for {repo}."

    lines = [f"CI/CD status for {repo}:\n"]
    lines.append(format_workflow_runs_block(runs))

    failed = activity.get("failed_runs") or []
    logs = format_ci_logs_block(failed)
    if logs and "No recent failed" not in logs:
        lines.append("\nBuild/deployment logs:\n" + logs)

    workflows = activity.get("workflows") or []
    if workflows:
        lines.append(
            "\nConfigured workflows: " + ", ".join(w["name"] for w in workflows)
        )
    return "\n".join(lines)


def answer_releases(activity: dict, repo: str) -> str:
    releases = activity.get("releases") or []
    if not releases:
        return f"No releases found for {repo}."
    return f"Releases for {repo}:\n\n{format_releases_block(releases)}"


def answer_activity_overview(activity: dict, ctx: dict, memory_block: str) -> str:
    repo = ctx.get("repo", "the repository")
    parts = [f"Full activity overview for {repo}:\n"]

    repo_stats = ctx.get("repo_stats")
    if repo_stats:
        parts.append(format_repo_stats_block(repo_stats))

    parts.append(format_activity_for_llm(activity))

    if ctx.get("commits"):
        parts.append("\nRecent commits:\n" + format_commits_block(ctx["commits"][:8]))

    prs = ctx.get("pull_requests") or []
    open_prs = [p for p in prs if p.get("status") == "open"][:5]
    if open_prs:
        parts.append("\nOpen pull requests:\n" + format_prs_block(open_prs))

    if memory_block and "No relevant" not in memory_block:
        parts.append(f"\nRelated project memory:\n{memory_block}")

    return "\n".join(parts)


def needs_commit_history(message: str) -> bool:
    return bool(COMMIT_HISTORY_PATTERN.search(message))


def needs_stack_inspection(message: str) -> bool:
    return bool(STACK_PATTERN.search(message))


def needs_repo_inspection(message: str) -> bool:
    return needs_stack_inspection(message) or needs_commit_history(message)


def _parse_package_json(content: str) -> dict:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "dependencies": dict(list((data.get("dependencies") or {}).items())[:50]),
        "dev_dependencies": dict(list((data.get("devDependencies") or {}).items())[:30]),
        "scripts": dict(list((data.get("scripts") or {}).items())[:20]),
    }


async def gather_chat_context(
    access_token: str,
    project: Project,
    message: str,
) -> dict:
    """Gather comprehensive repository context for a chat message."""
    import asyncio

    full_name = project.repo_full_name
    branch = project.default_branch or "main"

    repo, languages, root_files, readme, tree, commits, pull_requests, issues = (
        await asyncio.gather(
            get_repo(access_token, full_name),
            get_repo_languages(access_token, full_name),
            list_root_files(access_token, full_name),
            get_readme(access_token, full_name),
            build_repo_tree(access_token, full_name, max_depth=3),
            list_commits(access_token, full_name, branch=branch, per_page=20),
            list_pull_requests(access_token, full_name, state="all", per_page=15),
            list_issues(access_token, full_name, state="open", per_page=10),
        )
    )

    async def _maybe_repo_stats() -> dict | None:
        if not (needs_repo_stats(message) or needs_repo_activity(message)):
            return None
        try:
            return await gather_repo_stats(access_token, project)
        except Exception:  # noqa: BLE001
            return None

    repo_activity, repo_stats = await asyncio.gather(
        gather_repository_activity(access_token, full_name, branch=branch),
        _maybe_repo_stats(),
    )
    if not isinstance(repo_activity, dict):
        repo_activity = {}

    file_churn: dict | None = None
    if is_file_churn_question(message):
        try:
            file_churn = await analyze_file_churn(
                access_token, full_name, branch=branch, max_commits=150
            )
        except Exception:  # noqa: BLE001
            file_churn = None

    config_files: dict[str, str | dict] = {}
    for filename in KEY_CONFIG_FILES:
        if filename in root_files:
            content = await get_file_content(access_token, full_name, filename)
            if not content:
                continue
            if filename == "package.json":
                config_files["package.json"] = _parse_package_json(content)
                config_files["package.json_raw"] = content[:6000]
            else:
                config_files[filename] = content[:4000]

    source_files: dict[str, str] = {}
    tree_paths = set(tree)
    for candidate in SOURCE_ENTRY_CANDIDATES:
        if candidate in tree_paths or candidate.split("/")[-1] in root_files:
            content = await get_file_content(access_token, full_name, candidate)
            if content:
                source_files[candidate] = content[:5000]

    # Explore common source directories for structure
    dir_listings: dict[str, list[str]] = {}
    for dirname in EXPLORE_DIRS:
        items = await list_directory(access_token, full_name, dirname)
        if items:
            dir_listings[dirname] = [
                f"{i['type']}: {i['path']}" for i in items[:40]
            ]
            # Fetch a few key files from src/
            if dirname in ("src", "app"):
                for item in items[:12]:
                    if item["type"] == "file" and item["path"] not in source_files:
                        path = item["path"]
                        if any(
                            path.endswith(ext)
                            for ext in (".ts", ".js", ".py", ".go", ".rs")
                        ):
                            content = await get_file_content(
                                access_token, full_name, path
                            )
                            if content:
                                source_files[path] = content[:3000]

    evidence_sources = ["repository metadata", "file tree"]
    evidence_sources.extend(activity_evidence_sources(repo_activity))
    if repo_stats:
        evidence_sources.append("GitHub commit count")
        evidence_sources.append("GitHub contributors")
    if file_churn:
        evidence_sources.append("File churn analysis")
    if commits:
        evidence_sources.append("commit history")
    if pull_requests:
        evidence_sources.append("pull requests")
    if "package.json" in config_files:
        evidence_sources.append("package.json")
    if readme:
        evidence_sources.append("README")
    if source_files:
        evidence_sources.extend(list(source_files.keys())[:8])

    commit_detail: dict | None = None
    if should_fetch_commit_detail(message):
        from app.services.github import get_commit_detail

        sha = extract_commit_sha(message)
        if not sha and commits:
            sha = get_latest_commit_sha({"commits": commits})
        if sha:
            try:
                commit_detail = await get_commit_detail(access_token, full_name, sha)
                for source in commit_evidence_sources(commit_detail):
                    if source not in evidence_sources:
                        evidence_sources.append(source)
            except Exception:  # noqa: BLE001
                commit_detail = None

    return {
        "repo": full_name,
        "branch": branch,
        "repo_meta": repo,
        "description": repo.get("description"),
        "primary_language": repo.get("language"),
        "languages": languages,
        "root_files": root_files,
        "tree": tree,
        "readme": (readme or "")[:8000],
        "config_files": config_files,
        "source_files": source_files,
        "dir_listings": dir_listings,
        "commits": commits,
        "pull_requests": pull_requests,
        "issues": issues,
        "repo_stats": repo_stats,
        "repo_activity": repo_activity,
        "file_churn": file_churn,
        "commit_detail": commit_detail,
        "evidence_sources": evidence_sources,
    }


def format_commits_block(commits: list[dict]) -> str:
    if not commits:
        return "No commits found."
    lines = []
    for c in commits[:15]:
        lines.append(
            f"• {c.get('sha', c.get('id', ''))[:7]} — "
            f"\"{c.get('title', '')}\" by {c.get('author', 'unknown')} "
            f"({c.get('date', c.get('time', ''))})"
        )
    return "\n".join(lines)


def format_prs_block(prs: list[dict]) -> str:
    if not prs:
        return "No pull requests found."
    lines = []
    for pr in prs[:10]:
        lines.append(
            f"• PR #{pr.get('number', '?')} — \"{pr.get('title', '')}\" "
            f"by {pr.get('author', 'unknown')} [{pr.get('status', 'unknown')}] "
            f"({pr.get('time', '')})"
        )
    return "\n".join(lines)


def format_context_for_llm(ctx: dict) -> str:
    lines = [
        f"Repository: {ctx['repo']}",
        f"Branch: {ctx['branch']}",
        f"Primary language: {ctx.get('primary_language') or 'unknown'}",
    ]

    if ctx.get("description"):
        lines.append(f"Description: {ctx['description']}")

    repo_meta = ctx.get("repo_meta") or {}
    if repo_meta.get("created_at"):
        lines.append(f"Repository created: {repo_meta['created_at']}")
    if repo_meta.get("pushed_at"):
        lines.append(f"Last pushed: {repo_meta['pushed_at']}")
    if repo_meta.get("html_url"):
        lines.append(f"GitHub URL: {repo_meta['html_url']}")

    languages = ctx.get("languages") or {}
    if languages:
        lines.append(
            "Languages: " + ", ".join(f"{k}" for k in list(languages.keys())[:10])
        )

    root = ctx.get("root_files") or []
    if root:
        lines.append(f"Root files: {', '.join(root[:40])}")

    tree = ctx.get("tree") or []
    if tree:
        lines.append("Repository structure (sample):\n" + "\n".join(tree[:60]))

    for dirname, listing in (ctx.get("dir_listings") or {}).items():
        lines.append(f"{dirname}/ contents:\n" + "\n".join(listing[:20]))

    config = ctx.get("config_files") or {}
    if "package.json" in config:
        pkg = config["package.json"]
        if isinstance(pkg, dict):
            if pkg.get("name"):
                lines.append(f"package.json name: {pkg['name']}")
            if pkg.get("dependencies"):
                deps = ", ".join(f"{k}@{v}" for k, v in pkg["dependencies"].items())
                lines.append(f"Dependencies: {deps}")
            if pkg.get("scripts"):
                lines.append(f"Scripts: {', '.join(pkg['scripts'].keys())}")

    if ctx.get("readme"):
        lines.append(f"README:\n{ctx['readme'][:4000]}")

    repo_stats = ctx.get("repo_stats")
    if repo_stats:
        lines.append(f"\nRepository statistics:\n{format_repo_stats_block(repo_stats)}")

    repo_activity = ctx.get("repo_activity")
    if repo_activity:
        lines.append(f"\nRepository activity (CI/CD, deployments, releases):\n{format_activity_for_llm(repo_activity)}")

    file_churn = ctx.get("file_churn")
    if file_churn:
        lines.append(f"\nFile change frequency:\n{format_file_churn_block(file_churn)}")

    commit_detail = ctx.get("commit_detail")
    if commit_detail:
        lines.append(
            "\nSpecific commit detail (from GitHub — includes files changed and diff when available):\n"
            + format_commit_detail_block(commit_detail)
        )

    for path, content in list((ctx.get("source_files") or {}).items())[:6]:
        lines.append(f"File {path}:\n{content[:2500]}")

    lines.append(f"\nRecent commits:\n{format_commits_block(ctx.get('commits') or [])}")
    lines.append(f"\nPull requests:\n{format_prs_block(ctx.get('pull_requests') or [])}")

    issues = ctx.get("issues") or []
    if issues:
        issue_lines = [
            f"• #{i['number']} — {i['title']} by {i['author']} [{i['state']}]"
            for i in issues[:8]
        ]
        lines.append("\nOpen issues:\n" + "\n".join(issue_lines))

    return "\n\n".join(lines)


def answer_last_commit_author(ctx: dict) -> tuple[str, str | None]:
    commits = ctx.get("commits") or []
    branch = ctx.get("branch", "main")
    repo = ctx.get("repo", "the repository")
    if not commits:
        return (
            f"I checked {repo} but couldn't find "
            "any commits on the default branch.",
            None,
        )
    latest = commits[0]
    author = latest.get("author", "unknown")
    date = latest.get("date") or latest.get("time", "")
    message = latest.get("title", "")
    sha = latest.get("sha") or latest.get("id", "")
    short_sha = sha[:7] if sha else ""

    return (
        f"On the {branch} branch, the most recent commit was made by {author}.\n\n"
        f"Repository: {repo}\n"
        f"Commit: {short_sha}\n"
        f"Message: {message}\n"
        f"Date: {date}"
    ), sha


def answer_recent_changes(ctx: dict, memory_block: str) -> str:
    commits = ctx.get("commits") or []
    prs = ctx.get("pull_requests") or []
    activity = ctx.get("repo_activity") or {}
    repo = ctx.get("repo", "the repository")

    parts = [f"Recent activity in {repo}:\n"]

    events = activity.get("events") or []
    if events:
        parts.append("Latest repository events:\n" + format_events_block(events[:10]))

    runs = activity.get("workflow_runs") or []
    if runs:
        parts.append("\nRecent CI/CD runs:\n" + format_workflow_runs_block(runs[:5]))

    deployments = activity.get("deployments") or []
    if deployments:
        parts.append("\nRecent deployments:\n" + format_deployments_block(deployments[:5]))

    if commits:
        parts.append("\nRecent commits:\n" + format_commits_block(commits[:10]))
    else:
        parts.append("No recent commits found.")

    recent_prs = [p for p in prs if p.get("status") == "open"][:5]
    if recent_prs:
        parts.append("\nOpen pull requests:\n" + format_prs_block(recent_prs))

    if memory_block and "No relevant" not in memory_block:
        parts.append(f"\nRelated project memory:\n{memory_block}")

    return "\n".join(parts)
