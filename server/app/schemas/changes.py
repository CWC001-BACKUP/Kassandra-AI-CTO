from pydantic import BaseModel, Field


class ChangeItem(BaseModel):
    id: str | int
    type: str
    title: str
    author: str
    branch: str
    status: str
    files: int = 0
    additions: int = 0
    deletions: int = 0
    html_url: str | None = None
    time: str = ""
    timestamp: str | None = None
    number: int | None = None


class ChangeStats(BaseModel):
    this_week: int
    open_prs: int
    total_additions: int
    total_deletions: int


class ChangesResponse(BaseModel):
    changes: list[ChangeItem]
    stats: ChangeStats
    repo_full_name: str | None = None
