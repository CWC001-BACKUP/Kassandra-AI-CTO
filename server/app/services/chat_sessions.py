"""Chat session persistence and history."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ChatMessage, ChatSession
from app.services.repo_context import parse_time_hint


async def list_sessions(db: AsyncSession, user_id: str, limit: int = 50) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(desc(ChatSession.updated_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_session(
    db: AsyncSession, user_id: str, session_id: str
) -> ChatSession | None:
    result = await db.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_session(
    db: AsyncSession,
    user_id: str,
    *,
    project_id: str | None = None,
    title: str = "New chat",
) -> ChatSession:
    session = ChatSession(user_id=user_id, project_id=project_id, title=title)
    db.add(session)
    await db.flush()
    return session


async def delete_session(db: AsyncSession, user_id: str, session_id: str) -> bool:
    session = await get_session(db, user_id, session_id)
    if not session:
        return False
    await db.delete(session)
    return True


async def add_message(
    db: AsyncSession,
    session: ChatSession,
    *,
    role: str,
    content: str,
    source: str | None = None,
    evidence: list | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        source=source,
        evidence_json=json.dumps(evidence) if evidence else None,
    )
    db.add(msg)
    await db.flush()
    return msg


def _title_from_message(message: str) -> str:
    title = message.strip().replace("\n", " ")
    if len(title) > 60:
        return title[:57] + "..."
    return title or "New chat"


async def ensure_session(
    db: AsyncSession,
    user_id: str,
    session_id: str | None,
    *,
    project_id: str | None = None,
    first_message: str | None = None,
) -> ChatSession:
    if session_id:
        session = await get_session(db, user_id, session_id)
        if session:
            return session

    title = _title_from_message(first_message) if first_message else "New chat"
    return await create_session(db, user_id, project_id=project_id, title=title)


def messages_to_history(
    messages: list[ChatMessage],
    limit: int = 20,
    *,
    exclude_intro: bool = True,
) -> list[dict[str, str]]:
    filtered = messages
    if exclude_intro:
        filtered = [m for m in messages if m.source != "intro"]
    recent = filtered[-limit:] if len(filtered) > limit else filtered
    return [{"role": m.role, "content": m.content, "source": m.source} for m in recent]


def parse_evidence(msg: ChatMessage) -> list[dict[str, Any]]:
    if not msg.evidence_json:
        return []
    try:
        data = json.loads(msg.evidence_json)
        if not isinstance(data, list):
            return []
        out: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, str):
                out.append({"label": item, "url": None, "source": "github", "kind": None})
            elif isinstance(item, dict) and item.get("label"):
                out.append(item)
        return out
    except json.JSONDecodeError:
        return []


def _format_session_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone()
    return local.strftime("%I:%M %p").lstrip("0")


def _session_has_user_messages(session: ChatSession) -> bool:
    return any(m.role == "user" and m.source != "intro" for m in session.messages)


def _session_matches_time(session: ChatSession, time_hint, tolerance_minutes: int = 75) -> bool:
    """True if session activity today is near the hinted local time."""
    ref = session.updated_at or session.created_at
    if not ref or not time_hint:
        return False
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    local = ref.astimezone()
    today = datetime.now().astimezone().date()
    if local.date() != today:
        return False
    ref_minutes = local.hour * 60 + local.minute
    hint_minutes = time_hint.hour * 60 + time_hint.minute
    return abs(ref_minutes - hint_minutes) <= tolerance_minutes


def _session_to_recap_dict(session: ChatSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "updated_at": session.updated_at.isoformat() if session.updated_at else "",
        "time_label": _format_session_time(session.updated_at or session.created_at),
        "messages": messages_to_history(session.messages, limit=30),
    }


async def load_sessions_for_recap(
    db: AsyncSession,
    user_id: str,
    *,
    exclude_session_id: str,
    message: str = "",
    project_id: str | None = None,
    limit: int = 3,
) -> list[dict]:
    """Find other chat sessions to recap, optionally matching a time hint."""
    time_hint = parse_time_hint(message)
    session_list = await list_sessions(db, user_id, limit=40)

    loaded: list[tuple[ChatSession, int]] = []
    for summary in session_list:
        if summary.id == exclude_session_id:
            continue
        if project_id and summary.project_id not in (project_id, None):
            continue

        session = await get_session(db, user_id, summary.id)
        if not session or not _session_has_user_messages(session):
            continue

        if time_hint:
            if not _session_matches_time(session, time_hint):
                continue
            ref = session.updated_at or session.created_at
            if ref and ref.tzinfo is None:
                ref = ref.replace(tzinfo=timezone.utc)
            local = ref.astimezone() if ref else None
            hint_minutes = time_hint.hour * 60 + time_hint.minute
            ref_minutes = local.hour * 60 + local.minute if local else 9999
            loaded.append((session, abs(ref_minutes - hint_minutes)))
        else:
            loaded.append((session, 0))

    if time_hint and loaded:
        loaded.sort(key=lambda item: item[1])
        return [_session_to_recap_dict(s) for s, _ in loaded[:limit]]

    if not time_hint:
        results: list[dict] = []
        for summary in session_list:
            if summary.id == exclude_session_id:
                continue
            if project_id and summary.project_id not in (project_id, None):
                continue
            session = await get_session(db, user_id, summary.id)
            if session and _session_has_user_messages(session):
                results.append(_session_to_recap_dict(session))
            if len(results) >= limit:
                break
        return results

    return []
