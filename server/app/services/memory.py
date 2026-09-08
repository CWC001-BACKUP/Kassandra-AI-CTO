"""Sibyl Memory integration for Kassandra.

Setup (one-time, on the dev machine):
  pip install 'sibyl-memory-cli[mcp]'
  sibyl init          # browser sign-in → ~/.sibyl-memory/credentials.json

The server uses the Python SDK directly — no `sibyl setup` needed (that step
wires IDE agents like Claude Code; we call SibylMemoryProvider from FastAPI).

Docs: https://docs.sibyllabs.org/memory/
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sibyl_memory_hermes import SibylMemoryProvider

from app.config import Settings, get_settings

# Per-project provider cache (bounded by expected project count in dev)
_provider_cache: dict[str, SibylMemoryProvider] = {}


def _expand(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _db_path_for_tenant(settings: Settings, tenant_id: str) -> Path:
    data_dir = _expand(settings.sibyl_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    safe_tenant = tenant_id.replace("/", "__").replace("\\", "__")
    return data_dir / f"{safe_tenant}.db"


def get_memory_provider(tenant_id: str | None = None) -> SibylMemoryProvider:
    """Return a Sibyl provider for a project/repo tenant.

    Use one SQLite file per tenant (e.g. GitHub ``owner/repo`` slug).
    Falls back to ``settings.sibyl_tenant_id`` or ``default``.
    """
    settings = get_settings()
    resolved_tenant = tenant_id or settings.sibyl_tenant_id or "default"

    if resolved_tenant in _provider_cache:
        return _provider_cache[resolved_tenant]

    provider = SibylMemoryProvider(
        db_path=_db_path_for_tenant(settings, resolved_tenant),
        tenant_id=resolved_tenant,
        credentials_path=_expand(settings.sibyl_credentials),
        require_credentials=False,
        autoload_credentials=True,
    )
    _provider_cache[resolved_tenant] = provider
    return provider


@lru_cache
def sibyl_status() -> dict[str, object]:
    """Lightweight health info for /health — does not expose memory content."""
    settings = get_settings()
    credentials = _expand(settings.sibyl_credentials)
    data_dir = _expand(settings.sibyl_data_dir)

    try:
        provider = get_memory_provider()
        # Touch the provider so schema/DB are initialized
        provider.search("__health_probe__")
        ready = True
        error = None
    except Exception as exc:  # noqa: BLE001 — surface SDK errors in health check
        ready = False
        error = str(exc)

    return {
        "ready": ready,
        "data_dir": str(data_dir),
        "credentials_present": credentials.is_file(),
        "error": error,
    }
