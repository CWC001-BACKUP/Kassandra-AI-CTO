from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from app.api.router import api_router
from app.config import get_settings
from app.db.session import init_db

APP_DESCRIPTION = """
## Kassandra API

AI CTO backend: GitHub evidence + **Sibyl Memory** institutional knowledge.

### Load-bearing Sibyl routes

- `POST /chat` — chat with `sibyl_enabled` (search + teach gate)
- `POST /projects/{id}/teach` · `POST /memory/teach` · `POST /memory/confirm`
- `GET /projects/{id}/understanding` · `GET /memory/search`
- `POST /projects/{id}/memories/{id}/review`

### Docs

- **Scalar** (this UI): `/scalar`
- OpenAPI JSON: `/openapi.json`
- Swagger: `/docs`

Product overview: repository root `README.md`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=APP_DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/scalar", include_in_schema=False)
    async def scalar_docs():
        return get_scalar_api_reference(
            openapi_url=app.openapi_url,
            title=f"{settings.app_name} · Scalar",
        )

    return app


app = create_app()
