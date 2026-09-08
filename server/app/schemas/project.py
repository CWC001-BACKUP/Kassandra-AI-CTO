from datetime import datetime

from pydantic import BaseModel, Field


class GitHubRepoResponse(BaseModel):
    id: int
    full_name: str
    name: str
    owner: str
    html_url: str
    description: str | None = None
    private: bool = False
    default_branch: str = "main"
    language: str | None = None
    updated_at: str | None = None


class ProjectResponse(BaseModel):
    id: str
    repo_full_name: str
    repo_url: str
    description: str | None = None
    default_branch: str
    language: str | None = None
    is_active: bool
    analyzed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateProjectRequest(BaseModel):
    repo_full_name: str = Field(..., min_length=3, max_length=255)


class MemorySearchResponse(BaseModel):
    query: str
    tenant_id: str
    results: list[dict]
    count: int


class TeachRequest(BaseModel):
    text: str = Field(default="", max_length=8000)
    project_id: str | None = None
    gap_memory_id: str | None = None
    question: str | None = Field(default=None, max_length=500)
    extra: str | None = Field(default=None, max_length=4000)
    confirm: bool | None = None
    pending_id: str | None = None
    selected_indices: list[int] | None = None


class TeachResponse(BaseModel):
    stored: bool
    awaiting_confirmation: bool = False
    reason: str | None = None
    memory: dict | None = None
    memories: list[dict] = Field(default_factory=list)
    pending: dict | None = None
    conflicts: list[dict] = Field(default_factory=list)
    duplicate: bool = False
    gap_resolved: bool = False
    gaps_removed: int = 0
    reply: str | None = None
    verified: bool = False
    selected_count: int | None = None
    discarded_count: int | None = None


class ConfirmMemoryRequest(BaseModel):
    text: str = Field(default="", max_length=8000)
    project_id: str | None = None
    confirm: bool = True
    pending_id: str | None = None


class ProjectUnderstandingResponse(BaseModel):
    repo_full_name: str
    headline: str
    architecture: list[dict]
    historical_evolution: list[dict]
    problems: list[dict] = Field(default_factory=list)
    inferred: list[dict] = Field(default_factory=list)
    confirmed: list[dict] = Field(default_factory=list)
    reviewable_facts: list[dict] = Field(default_factory=list)
    counts: dict
    knowledge_gaps: list[dict]
    confidence_areas: dict
    interview_intro: str
    updated_at: str | None = None


class MemoryReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(confirm|reject|correct)$")
    note: str | None = Field(default=None, max_length=2000)


class MemoryReviewResponse(BaseModel):
    ok: bool
    action: str | None = None
    reason: str | None = None
    memory: dict | None = None
    correction: dict | None = None
