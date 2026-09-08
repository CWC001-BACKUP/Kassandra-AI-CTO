# Kassandra Server

FastAPI backend for **Kassandra** (AI CTO). Handles GitHub integration, LLM orchestration, application data (PostgreSQL), and **local-first project memory** via [Sibyl Memory](https://sibyllabs.org/).

Product / hackathon overview (load-bearing map, Prior Work, demo beat): **[../README.md](../README.md)**

## API documentation (Scalar)

With the server running:

| URL | Docs |
|-----|------|
| **[http://localhost:8000/scalar](http://localhost:8000/scalar)** | **Scalar** interactive API reference (primary) |
| [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI |
| [http://localhost:8000/redoc](http://localhost:8000/redoc) | ReDoc |
| [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) | OpenAPI 3 schema |
| [http://localhost:8000/health](http://localhost:8000/health) | Health + Sibyl status |

Scalar is wired in [`app/main.py`](app/main.py) via [`scalar-fastapi`](https://pypi.org/project/scalar-fastapi/).

## Requirements

- Python 3.10+
- PostgreSQL (e.g. [Neon](https://neon.tech)) for app data
- Optional: Sibyl CLI for account activation (memory works without it)

## Quick start

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env with DATABASE_URL, GitHub OAuth, JWT_SECRET, and LLM settings

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open **[http://localhost:8000/scalar](http://localhost:8000/scalar)**.

The Vite client proxies `/api` → `http://localhost:8000` in development ([`../client/vite.config.ts`](../client/vite.config.ts)).

## Environment variables

Copy [`.env.example`](.env.example) → `.env`. Key settings:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Neon/PostgreSQL connection string (see [Wipe database](#wipe-database)) |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth |
| `GITHUB_REDIRECT_URI` | OAuth callback (default `http://localhost:8000/auth/github/callback`) |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | LLM provider (OpenAI-compatible) |
| `SIBYL_DATA_DIR` | Local SQLite memory files (default `./data/sibyl`) |
| `SIBYL_CREDENTIALS` | Sibyl activation file (default `~/.sibyl-memory/credentials.json`) |
| `SIBYL_TENANT_ID` | Optional default tenant; per-repo tenants are set in code |
| `FRONTEND_URL` | Client origin (default `http://localhost:5173`) |
| `JWT_SECRET` | Session signing secret |

**There is no `SIBYL_API_KEY`.** Sibyl Memory is local-first; activation uses a credentials file, not an API key.

## Sibyl Memory

Kassandra uses Sibyl as **load-bearing long-term memory** — architectural decisions, incidents, constraints, etc. Memory is stored in **SQLite on disk**, not in a remote Sibyl API.

### Critical paths (where memory is written / read)

| Path | File |
|------|------|
| Provider / tenant SQLite | [`app/services/memory.py`](app/services/memory.py) |
| Institutional schema + gaps | [`app/services/institutional_memory.py`](app/services/institutional_memory.py) |
| Pending confirm gate | [`app/services/pending_memory.py`](app/services/pending_memory.py) |
| Teach orchestration | [`app/services/teach.py`](app/services/teach.py) |
| Chat search + `sibyl_enabled` | [`app/services/chat.py`](app/services/chat.py) |
| Evidence tags (`sibyl` vs `github`) | [`app/services/evidence.py`](app/services/evidence.py) |
| HTTP: teach / understanding / search | [`app/api/projects.py`](app/api/projects.py) |
| HTTP: chat | [`app/api/chat.py`](app/api/chat.py) |

### How this differs from the Sibyl website setup

The [Sibyl Memory Plugin setup](https://sibyllabs.org/) has four steps:

| Sibyl docs step | Kassandra server |
|-----------------|------------------|
| 1. `pip install 'sibyl-memory-cli[mcp]'` | Optional — `sibyl-memory-hermes` is already in `requirements.txt` |
| 2. `sibyl init` | Optional — activates your Sibyl account (see below) |
| 3. `sibyl setup` | **Not needed** — that wires IDE agents (Claude Code, Codex); we call the Python SDK from FastAPI |
| 4. Test in your AI app | Use `/health`, `/scalar`, and chat with Sibyl on |

### You can develop without `sibyl init`

The server runs Sibyl **without activation**. Each project/repo gets its own SQLite file under `SIBYL_DATA_DIR`:

```
data/sibyl/
  default.db          # fallback tenant
  owner__repo.db      # per GitHub repo (slashes → __)
```

`GET /health` reports Sibyl status:

```json
{
  "status": "ok",
  "sibyl": {
    "ready": true,
    "data_dir": ".../server/data/sibyl",
    "credentials_present": false,
    "error": null
  }
}
```

`credentials_present: false` is fine for local development. The free unactivated tier still provides the full five-tier memory model (2 MB local cap).

### Optional: activate your Sibyl account

```powershell
pip install 'sibyl-memory-cli[mcp]'
sibyl init
sibyl status
sibyl health
```

Opens `https://auth.sibyllabs.org`, writes `~/.sibyl-memory/credentials.json`.

### Troubleshooting `sibyl init` — `TimeoutError`

If `sibyl init` times out reaching `https://api.sibyllabs.org/api/plugin/session-init`:

1. Continue without activation — local memory still works (`credentials_present: false`).
2. Test: `curl -I https://api.sibyllabs.org` (403 on bare GET is normal).
3. Retry without VPN / on another network.

### Using Sibyl in code

```python
from app.services.memory import get_memory_provider

memory = get_memory_provider("my-org/my-repo")
memory.remember("architecture", "database", {"choice": "PostgreSQL", "reason": "..."})
hits = memory.search("PostgreSQL")
fact = memory.recall("architecture", "database")
```

| AI CTO concept | Sibyl tier | SDK method |
|----------------|------------|------------|
| Decisions, architecture | WARM entity | `remember()` / `recall()` |
| Incidents, changelog | COLD journal | `save_context()` |
| Session context | HOT state | `set_state()` |
| Docs / runbooks | REFERENCE | `set_reference()` |
| Retired knowledge | ARCHIVE | `archive()` |
| Search | FTS5 | `search()` |

Docs: [docs.sibyllabs.org/memory](https://docs.sibyllabs.org/memory/) · [Integrations](https://docs.sibyllabs.org/memory/integrations)

### Production persistence

`SIBYL_DATA_DIR` must live on **persistent disk**. Do not use ephemeral filesystems for `./data/sibyl` in production.

## Project layout

```
server/
├── app/
│   ├── main.py                 # FastAPI + Scalar at /scalar
│   ├── config.py               # Settings (pydantic-settings)
│   ├── api/
│   │   ├── router.py
│   │   ├── health.py           # GET /health
│   │   ├── auth.py             # /auth/*
│   │   ├── chat.py             # /chat (+ sibyl_enabled)
│   │   ├── projects.py         # projects, teach, understanding, memory
│   │   ├── dashboard.py
│   │   ├── changes.py
│   │   ├── logs.py
│   │   ├── reports.py
│   │   └── webhooks.py
│   ├── services/
│   │   ├── memory.py           # Sibyl Memory wrapper
│   │   ├── institutional_memory.py
│   │   ├── pending_memory.py
│   │   ├── teach.py
│   │   ├── chat.py
│   │   ├── evidence.py
│   │   ├── repo_context.py     # GitHub deterministic answers
│   │   └── …
│   ├── models/ · schemas/ · db/
├── tests/
├── scripts/
│   ├── feature_scenario.py     # Live feature battery (incl. Sibyl off)
│   └── wipe_db.py
├── data/sibyl/                 # Local Sibyl SQLite (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

## API route map

Prefer **Scalar** for live schemas. Summary:

| Area | Prefix / paths |
|------|----------------|
| Health | `GET /health` |
| Auth | `/auth/register`, `/login`, `/github`, `/me`, … |
| Chat | `GET|POST /chat/sessions`, `POST /chat` |
| Projects | `GET|POST /projects`, `POST .../analyze`, `.../activate` |
| Sibyl / teach | `POST .../teach`, `GET .../understanding`, `POST .../memories/{id}/review` |
| Memory | `POST /memory/teach`, `POST /memory/confirm`, `GET /memory/search` |
| Dashboard | `/dashboard/stats`, `/dashboard/activity` |
| Changes / logs / reports | `/changes`, `/logs`, `/reports` |
| Webhooks | `POST /webhooks/github` |

## Scripts

```powershell
uvicorn app.main:app --reload --port 8000

pytest

# Live feature scenario (Trade Engine project in DB)
python -m scripts.feature_scenario

# Optional Sibyl CLI
sibyl init
sibyl status
```

### Wipe database

**Destructive** — deletes app data in PostgreSQL (and optionally Sibyl `*.db` files):

```powershell
python -m scripts.wipe_db          # preview
python -m scripts.wipe_db --yes
python -m scripts.wipe_db --yes --sibyl
```

## Links

- [Root README (hackathon)](../README.md)
- [Sibyl Labs](https://sibyllabs.org/)
- [Sibyl Memory docs](https://docs.sibyllabs.org/memory/)
- [Sibyl Memory on GitHub](https://github.com/Sibyl-Labs/Sibyl-Memory)
- [Scalar FastAPI plugin](https://scalar.com/products/api-references/integrations/fastapi)
- [Hackathon rules](https://hack.sibyllabs.org/rules)
