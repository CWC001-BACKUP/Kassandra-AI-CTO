from fastapi import APIRouter

from app.services.memory import sibyl_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, object]:
    return {
        "status": "ok",
        "sibyl": sibyl_status(),
    }
