"""Generate engineering reports from memory and GitHub changes."""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, Report, User
from app.services.activity import log_activity
from app.services.changes import get_project_changes
from app.services.llm import LLMError, chat_completion, is_llm_configured
from app.services.memory import get_memory_provider

REPORT_PROMPTS = {
    "sprint": (
        "Generate a Sprint Summary report covering recent changes, key decisions, "
        "blockers, and recommended next steps."
    ),
    "incident": (
        "Generate an Incident Report with timeline, impact, root cause analysis, "
        "and action items based on available project memory."
    ),
    "architecture": (
        "Generate an Architecture Review covering current system design, recent "
        "decisions, dependencies, and technical debt."
    ),
    "onboarding": (
        "Generate an Onboarding Brief for a new engineer joining this project."
    ),
}

REPORT_TITLES = {
    "sprint": "Sprint Summary",
    "incident": "Incident Report",
    "architecture": "Architecture Review",
    "onboarding": "Onboarding Brief",
}


async def list_reports(db: AsyncSession, user_id: str, limit: int = 20) -> list[Report]:
    result = await db.execute(
        select(Report)
        .where(Report.user_id == user_id)
        .order_by(desc(Report.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_report(db: AsyncSession, user_id: str, report_id: str) -> Report | None:
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def generate_report(
    db: AsyncSession,
    user: User,
    project: Project,
    report_type: str,
) -> Report:
    if report_type not in REPORT_PROMPTS:
        raise ValueError(f"Unknown report type: {report_type}")

    title = f"{REPORT_TITLES[report_type]} — {project.repo_full_name}"
    report = Report(
        user_id=user.id,
        project_id=project.id,
        report_type=report_type,
        title=title,
        status="generating",
    )
    db.add(report)
    await db.flush()

    memory = get_memory_provider(project.repo_full_name)
    memory_hits = memory.search(report_type)
    memory_text = "\n".join(
        str(h.get("content", h) if isinstance(h, dict) else h) for h in (memory_hits or [])[:10]
    )

    changes_summary = ""
    try:
        changes_data = await get_project_changes(user, project)
        recent = changes_data["changes"][:10]
        changes_summary = "\n".join(
            f"- [{c['type']}] {c['title']} ({c['author']}, {c['time']})" for c in recent
        )
    except Exception:  # noqa: BLE001
        changes_summary = "No recent changes available."

    if not is_llm_configured():
        content = (
            f"# {title}\n\n"
            f"## Project Memory\n{memory_text or 'No memory entries found.'}\n\n"
            f"## Recent Changes\n{changes_summary}\n\n"
            "_Configure LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL for AI-generated reports._"
        )
        report.content = content
        report.status = "ready"
    else:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Kassandra, an AI CTO. Write clear, structured engineering reports "
                    "in Markdown. Use headings, bullet points, and actionable recommendations."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{REPORT_PROMPTS[report_type]}\n\n"
                    f"Repository: {project.repo_full_name}\n\n"
                    f"Project memory:\n{memory_text or 'None'}\n\n"
                    f"Recent changes:\n{changes_summary or 'None'}"
                ),
            },
        ]
        try:
            report.content = await chat_completion(messages)
            report.status = "ready"
        except LLMError as exc:
            report.content = f"Report generation failed: {exc.message}"
            report.status = "failed"

    await log_activity(
        db,
        user_id=user.id,
        project_id=project.id,
        source="reports",
        message=f"Report generated: {title}",
        metadata={"report_id": report.id, "type": report_type},
    )

    memory.save_context(
        inputs={"event": "report_generated", "type": report_type},
        outputs={"title": title, "status": report.status},
    )

    return report
