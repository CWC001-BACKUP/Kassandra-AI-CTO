from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.chat import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionDetailResponse,
    ChatSessionResponse,
    CreateSessionRequest,
)
from app.services.chat import get_initial_chat_message, process_chat_message
from app.services.cross_repo import process_cross_repo_message, resolve_cross_repo_projects
from app.services.chat_sessions import (
    add_message,
    create_session,
    delete_session,
    ensure_session,
    get_session,
    list_sessions,
    load_sessions_for_recap,
    messages_to_history,
    parse_evidence,
)
from app.services.repo_context import should_load_other_sessions
from app.services.projects import get_active_project, get_user_project, list_user_projects

router = APIRouter(prefix="/chat", tags=["chat"])


def _session_response(session, message_count: int = 0) -> ChatSessionResponse:
    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        project_id=session.project_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=message_count,
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSessionResponse]:
    sessions = await list_sessions(db, current_user.id)
    return [_session_response(s) for s in sessions]


@router.post("/sessions", response_model=ChatSessionDetailResponse, status_code=201)
async def create_chat_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetailResponse:
    project_id = body.project_id
    if not project_id:
        active = await get_active_project(db, current_user.id)
        project_id = active.id if active else None

    session = await create_session(
        db, current_user.id, project_id=project_id, title=body.title
    )
    welcome = get_initial_chat_message(current_user.full_name or current_user.github_username)
    msg = await add_message(db, session, role="assistant", content=welcome, source="intro")

    return ChatSessionDetailResponse(
        **_session_response(session, message_count=1).model_dump(),
        messages=[
            ChatMessageResponse(
                id=msg.id,
                role="assistant",
                content=welcome,
                source="intro",
                evidence=[],
                created_at=msg.created_at,
            )
        ],
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionDetailResponse:
    session = await get_session(db, current_user.id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return ChatSessionDetailResponse(
        **_session_response(session, message_count=len(session.messages)).model_dump(),
        messages=[
            ChatMessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                source=m.source,
                evidence=parse_evidence(m),
                created_at=m.created_at,
            )
            for m in session.messages
        ],
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def remove_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await delete_session(db, current_user.id, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    project = None
    if body.project_id:
        project = await get_user_project(db, current_user.id, body.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    else:
        project = await get_active_project(db, current_user.id)

    session = await ensure_session(
        db,
        current_user.id,
        body.session_id,
        project_id=project.id if project else None,
        first_message=body.message,
    )

    # Once a session is bound to a project, keep all messages scoped to that repo.
    if session.project_id:
        bound = await get_user_project(db, current_user.id, session.project_id)
        if bound:
            project = bound

    history = messages_to_history(session.messages)

    other_sessions: list[dict] = []
    if should_load_other_sessions(body.message, history):
        other_sessions = await load_sessions_for_recap(
            db,
            current_user.id,
            exclude_session_id=session.id,
            message=body.message,
            project_id=project.id if project else None,
        )

    all_projects = await list_user_projects(db, current_user.id)
    cross_projects = resolve_cross_repo_projects(
        body.message,
        project,
        all_projects,
        body.project_ids,
    )

    if len(cross_projects) >= 2:
        result = await process_cross_repo_message(
            current_user,
            body.message,
            cross_projects,
            history=history,
            sibyl_enabled=body.sibyl_enabled,
        )
    else:
        result = await process_chat_message(
            current_user,
            body.message,
            project,
            history=history,
            stored_commit_sha=session.last_commit_sha,
            stored_previous_commit_sha=session.previous_commit_sha,
            other_sessions=other_sessions,
            sibyl_enabled=body.sibyl_enabled,
        )

    if session.title == "New chat":
        from app.services.chat_sessions import _title_from_message

        session.title = _title_from_message(body.message)

    if result.get("last_commit_sha"):
        session.last_commit_sha = result["last_commit_sha"]
    if result.get("previous_commit_sha"):
        session.previous_commit_sha = result["previous_commit_sha"]

    await add_message(db, session, role="user", content=body.message)
    await add_message(
        db,
        session,
        role="assistant",
        content=result["reply"],
        source=result.get("source"),
        evidence=result.get("evidence"),
    )

    return ChatResponse(
        reply=result["reply"],
        source=result["source"],
        intent=result.get("intent"),
        project_id=result.get("project_id"),
        session_id=session.id,
        memory_hits=result.get("memory_hits", 0),
        evidence=result.get("evidence", []),
        evidence_level=result.get("evidence_level"),
        evidence_level_name=result.get("evidence_level_name"),
    )
