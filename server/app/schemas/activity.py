from pydantic import BaseModel, Field


class ActivityLogResponse(BaseModel):
    id: str
    level: str
    source: str
    message: str
    project_id: str | None = None
    metadata: dict | None = None
    timestamp: str


class GenerateReportRequest(BaseModel):
    report_type: str = Field(..., pattern="^(sprint|incident|architecture|onboarding)$")
    project_id: str | None = None


class ReportResponse(BaseModel):
    id: str
    report_type: str
    title: str
    content: str
    status: str
    project_id: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class AnalysisResponse(BaseModel):
    repo_full_name: str
    analyzed_at: str
    languages: dict[str, int]
    root_files: list[str]
    config_files: list[str]
    readme_found: bool
    webhook_registered: bool
    understanding: dict | None = None
    counts: dict | None = None
    history_meta: dict | None = None
