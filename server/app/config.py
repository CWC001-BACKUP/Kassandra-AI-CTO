from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI CTO"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]

    # Database (Neon PostgreSQL)
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/aicto"

    # JWT / sessions
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    otp_expire_minutes: int = 15

    # Frontend (OAuth redirects, CORS companion)
    frontend_url: str = "http://localhost:5173"

    # Email (Brevo transactional API — https://developers.brevo.com)
    brevo_api_key: str = Field(default="", validation_alias="BREVO")
    from_name: str = "Kassandra"
    from_email: str = ""
    reply_to_email: str = ""

    # GitHub
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/auth/github/callback"
    github_webhook_secret: str = ""
    webhook_base_url: str = ""

    # LLM
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # Sibyl Memory (local-first — see https://docs.sibyllabs.org/memory/install)
    # Run once: pip install 'sibyl-memory-cli[mcp]' && sibyl init
    sibyl_data_dir: str = "./data/sibyl"
    sibyl_credentials: str = "~/.sibyl-memory/credentials.json"
    sibyl_tenant_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
