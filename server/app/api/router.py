from fastapi import APIRouter

from app.api import auth, changes, chat, dashboard, health, logs, projects, reports, webhooks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(projects.router)
api_router.include_router(changes.router)
api_router.include_router(logs.router)
api_router.include_router(reports.router)
api_router.include_router(webhooks.router)
api_router.include_router(dashboard.router)
