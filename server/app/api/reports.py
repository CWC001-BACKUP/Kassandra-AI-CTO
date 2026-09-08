from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.activity import GenerateReportRequest, ReportResponse
from app.services.projects import get_active_project, get_user_project
from app.services.reports import generate_report, get_report, list_reports

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_response(report) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        report_type=report.report_type,
        title=report.title,
        content=report.content,
        status=report.status,
        project_id=report.project_id,
        created_at=report.created_at.isoformat(),
    )


@router.get("", response_model=list[ReportResponse])
async def get_reports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReportResponse]:
    reports = await list_reports(db, current_user.id)
    return [_report_response(r) for r in reports]


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report_by_id(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    report = await get_report(db, current_user.id, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_response(report)


@router.post("/generate", response_model=ReportResponse, status_code=201)
async def create_report(
    body: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    if body.project_id:
        project = await get_user_project(db, current_user.id, body.project_id)
    else:
        project = await get_active_project(db, current_user.id)

    if not project:
        raise HTTPException(
            status_code=400,
            detail="No project selected. Add and activate a repository under Projects.",
        )

    try:
        report = await generate_report(db, current_user, project, body.report_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _report_response(report)
