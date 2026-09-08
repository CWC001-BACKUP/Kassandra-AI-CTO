"""Detect basic conversational messages (greetings, thanks, etc.).

Returns a canned reply so we skip the LLM for simple social exchanges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class IntroIntent(str, Enum):
    GREETING = "greeting"
    FAREWELL = "farewell"
    THANKS = "thanks"
    HOW_ARE_YOU = "how_are_you"
    WHO_ARE_YOU = "who_are_you"
    HELP = "help"


@dataclass(frozen=True)
class IntroMatch:
    intent: IntroIntent
    response: str


_RECAP_SKIP_PATTERNS = (
    r"\b(continue|left off|last conversation|previous conversation|recap|"
    r"where we (left off|were)|another session|other session|pick up where)\b",
)

_GREETING_PATTERNS = (
    r"^(hi|hello|hey|hiya|howdy|greetings|good\s+(morning|afternoon|evening|day)|sup|yo)\b",
    r"^(what'?s\s+up|wassup)\b",
)

_FAREWELL_PATTERNS = (
    r"^(bye|goodbye|good\s*bye|see\s+ya|see\s+you|later|catch\s+you\s+later|cya)\b",
    r"^(good\s*night|gn)\b",
)

_THANKS_PATTERNS = (
    r"^(thanks?|thank\s+you|thx|ty|appreciate\s+it|much\s+appreciated|cheers)\b",
    r"^(that'?s\s+helpful|you'?re\s+the\s+best|awesome|great\s+job)\b",
)

_HOW_ARE_YOU_PATTERNS = (
    r"^how\s+are\s+you\b",
    r"^how'?s\s+it\s+going\b",
    r"^how\s+do\s+you\s+do\b",
)

_WHO_ARE_YOU_PATTERNS = (
    r"^who\s+are\s+you\b",
    r"^what\s+are\s+you\b",
    r"^what\s+can\s+you\s+do\b",
    r"^what\s+do\s+you\s+do\b",
)

_HELP_PATTERNS = (
    r"^help\b",
    r"^what\s+can\s+i\s+(do|ask)\b",
    r"^how\s+does\s+this\s+work\b",
    r"^getting\s+started\b",
)


def _normalize(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"[^\w\s'?]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text) for p in patterns)


def get_welcome_message(
    user_name: str | None = None,
    *,
    repo_full_name: str | None = None,
    gap_count: int = 0,
) -> str:
    greeting = f"Hello, {user_name}." if user_name else "Hello."

    if not repo_full_name:
        return (
            f"{greeting} I'm Kassandra, your AI CTO.\n\n"
            "No repository is connected yet.\n\n"
            "Connect a GitHub repository under Projects and I'll reconstruct its architecture "
            "into Sibyl, then ask only for the institutional WHY the repo cannot provide.\n\n"
            "After that you can:\n"
            "• Ask about stack, changes, and decisions here in Chat\n"
            "• Open Teach Kassandra to fill knowledge gaps"
        )

    gap_line = ""
    if gap_count > 0:
        gap_line = (
            f"\n\nI still have {gap_count} knowledge gap"
            f"{'s' if gap_count != 1 else ''} for {repo_full_name}. "
            "Open Teach Kassandra to answer them, or tell me the WHY here in chat "
            "and I'll ask before saving to Sibyl."
        )

    return (
        f"{greeting} I'm Kassandra, your AI CTO.\n\n"
        f"Active repository: {repo_full_name}\n\n"
        "I combine GitHub evidence with Sibyl institutional memory — "
        "what the system does, how it evolved, and why your team decided it.\n\n"
        "Ask me:\n"
        "• Why are we using this database?\n"
        "• What changed recently?\n"
        "• Have we encountered this issue before?\n"
        "• Why was this architecture chosen?\n"
        "• Should we introduce this technology?"
        f"{gap_line}"
    )


def _greeting_response(
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


def _farewell_response() -> str:
    return "Goodbye! I'll be here when you need help with your project."


def _thanks_response() -> str:
    return "You're welcome! Let me know if there's anything else I can help with."


def _how_are_you_response(*, repo_full_name: str | None = None) -> str:
    if repo_full_name:
        return (
            f"I'm doing well and ready to help with {repo_full_name}. "
            "Ask about architecture, recent changes, or Sibyl project memory — "
            "or teach me missing institutional context."
        )
    return (
        "I'm doing well and ready to help. "
        "Connect a repository under Projects, then ask about architecture or memory."
    )


def _who_are_you_response() -> str:
    return (
        "I'm Kassandra, your AI CTO.\n\n"
        "I inspect your GitHub repositories, remember engineering decisions in "
        "Sibyl project memory, and help you reason about architecture, changes, and "
        "technical trade-offs — using evidence from your actual codebase, not guesses.\n\n"
        "Use Teach Kassandra when the repository cannot explain the WHY."
    )


def _help_response(*, repo_full_name: str | None = None, gap_count: int = 0) -> str:
    if not repo_full_name:
        return (
            "Here's how to get started:\n\n"
            "1. Connect GitHub in Settings if you haven't already.\n"
            "2. Go to Projects and add a repository.\n"
            "3. Kassandra bootstraps from the repo into Sibyl — architecture, history, and gaps.\n"
            "4. Open Teach Kassandra to answer only the missing WHY questions.\n"
            "5. Use AI Chat for reasoning that combines GitHub evidence with Sibyl memory.\n\n"
            "I only answer from repository evidence and confirmed institutional memory."
        )
    gap_bit = (
        f"\n• You have {gap_count} open knowledge gap{'s' if gap_count != 1 else ''} — "
        "answer them in Teach Kassandra or tell me here (I'll confirm before saving)."
        if gap_count
        else ""
    )
    return (
        f"You're connected to {repo_full_name}.\n\n"
        "You can:\n"
        "• Ask about stack, commits, PRs, and architecture here\n"
        "• Teach me institutional context — I'll extract candidates and ask before saving to Sibyl\n"
        "• Open Teach Kassandra for guided knowledge-gap questions"
        f"{gap_bit}"
    )


def check_intro_message(
    message: str,
    *,
    user_name: str | None = None,
    repo_full_name: str | None = None,
    gap_count: int = 0,
) -> IntroMatch | None:
    """Return a canned reply if the message is a basic conversational opener."""
    text = _normalize(message)
    if not text:
        return None

    # Short messages only — avoid misclassifying real engineering questions
    if len(text.split()) > 12:
        return None

    if _matches_any(text, _RECAP_SKIP_PATTERNS):
        return None

    if _matches_any(text, _GREETING_PATTERNS):
        return IntroMatch(
            IntroIntent.GREETING,
            _greeting_response(
                user_name,
                repo_full_name=repo_full_name,
                gap_count=gap_count,
            ),
        )

    if _matches_any(text, _FAREWELL_PATTERNS):
        return IntroMatch(IntroIntent.FAREWELL, _farewell_response())

    if _matches_any(text, _THANKS_PATTERNS):
        return IntroMatch(IntroIntent.THANKS, _thanks_response())

    if _matches_any(text, _HOW_ARE_YOU_PATTERNS):
        return IntroMatch(
            IntroIntent.HOW_ARE_YOU,
            _how_are_you_response(repo_full_name=repo_full_name),
        )

    if _matches_any(text, _WHO_ARE_YOU_PATTERNS):
        return IntroMatch(IntroIntent.WHO_ARE_YOU, _who_are_you_response())

    if _matches_any(text, _HELP_PATTERNS):
        return IntroMatch(
            IntroIntent.HELP,
            _help_response(repo_full_name=repo_full_name, gap_count=gap_count),
        )

    return None
