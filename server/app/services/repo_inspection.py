"""Backward-compatible re-exports — use repo_context for new code."""

from app.services.repo_context import (
    format_context_for_llm as format_evidence_block,
    gather_chat_context as gather_repo_evidence,
    is_project_name_question,
    needs_repo_inspection,
)

__all__ = [
    "gather_repo_evidence",
    "format_evidence_block",
    "is_project_name_question",
    "needs_repo_inspection",
]
