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
