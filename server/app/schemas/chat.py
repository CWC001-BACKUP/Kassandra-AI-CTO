from datetime import datetime

from typing import Any

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    label: str
    url: str | None = None
    source: str = "github"
    kind: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    project_id: str | None = None
    project_ids: list[str] | None = Field(default=None, max_length=5)
    session_id: str | None = None
    sibyl_enabled: bool = True


class ChatResponse(BaseModel):
    reply: str
    source: str
    intent: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    memory_hits: int = 0
    evidence: list[EvidenceRef] = []
    evidence_level: int | None = None
    evidence_level_name: str | None = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    source: str | None = None
    evidence: list[EvidenceRef] = []
    created_at: datetime


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    project_id: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: list[ChatMessageResponse] = []


class CreateSessionRequest(BaseModel):
    project_id: str | None = None
    title: str = "New chat"
