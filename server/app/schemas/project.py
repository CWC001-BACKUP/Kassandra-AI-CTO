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
    text: str = Field(..., min_length=1, max_length=8000)
    project_id: str | None = None
    gap_memory_id: str | None = None
    question: str | None = Field(default=None, max_length=500)
    extra: str | None = Field(default=None, max_length=4000)


class TeachResponse(BaseModel):
    stored: bool
    reason: str | None = None
    memory: dict | None = None
    conflicts: list[dict] = Field(default_factory=list)
    duplicate: bool = False
    gap_resolved: bool = False
    gaps_removed: int = 0


class ConfirmMemoryRequest(BaseModel):
    text: str = Field(..., min_length=8, max_length=8000)
    project_id: str | None = None
    confirm: bool = True


class ProjectUnderstandingResponse(BaseModel):
    repo_full_name: str
    headline: str
    architecture: list[dict]
    historical_evolution: list[dict]
    counts: dict
    knowledge_gaps: list[dict]
    confidence_areas: dict
    interview_intro: str
    updated_at: str | None = None
