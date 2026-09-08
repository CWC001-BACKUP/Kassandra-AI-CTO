# Kassandra Server

FastAPI backend for **Kassandra** (AI CTO). Handles GitHub integration, LLM orchestration, application data (PostgreSQL), and **local-first project memory** via [Sibyl Memory](https://sibyllabs.org/).

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
# Edit .env with your DATABASE_URL, GitHub OAuth, and LLM settings

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: [http://localhost:8000/health](http://localhost:8000/health)

The Vite client proxies `/api` → `http://localhost:8000` in development.

## Environment variables

Copy `.env.example` → `.env`. Key settings:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Neon/PostgreSQL connection string (see [Wipe database](#wipe-database)) |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth |
| `GITHUB_REDIRECT_URI` | OAuth callback (default `http://localhost:8000/auth/github/callback`) |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | LLM provider (OpenAI-compatible) |
| `SIBYL_DATA_DIR` | Local SQLite memory files (default `./data/sibyl`) |
| `SIBYL_CREDENTIALS` | Sibyl activation file (default `~/.sibyl-memory/credentials.json`) |
| `SIBYL_TENANT_ID` | Optional default tenant; per-repo tenants are set in code |

**There is no `SIBYL_API_KEY`.** Sibyl Memory is local-first; activation uses a credentials file, not an API key.

## Sibyl Memory

Kassandra uses Sibyl as **load-bearing long-term memory** — architectural decisions, incidents, changes, etc. Memory is stored in **SQLite on disk**, not in a remote Sibyl API.

### How this differs from the Sibyl website setup

The [Sibyl Memory Plugin setup](https://sibyllabs.org/) has four steps:

| Sibyl docs step | Kassandra server |
|-----------------|------------------|
| 1. `pip install 'sibyl-memory-cli[mcp]'` | Optional — `sibyl-memory-hermes` is already in `requirements.txt` |
| 2. `sibyl init` | Optional — activates your Sibyl account (see below) |
| 3. `sibyl setup` | **Not needed** — that wires IDE agents (Claude Code, Codex); we call the Python SDK from FastAPI |
| 4. Test in your AI app | Use `/health` and the memory service in code |

### You can develop without `sibyl init`

The server runs Sibyl **without activation**. Each project/repo gets its own SQLite file under `SIBYL_DATA_DIR`:

```
data/sibyl/
  default.db          # fallback tenant
  owner__repo.db      # per GitHub repo (slashes → __)
```

`/health` reports Sibyl status:

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

Activation lifts tier limits and enables server-side tier verification. One-time, in your terminal:

```powershell
pip install 'sibyl-memory-cli[mcp]'
sibyl init
```

This opens a browser at `auth.sibyllabs.org`, signs you in (wallet or email), and writes `~/.sibyl-memory/credentials.json`.

Verify:

```powershell
sibyl status
sibyl health
```

### Troubleshooting `sibyl init` — `TimeoutError`

If you see:

```
TimeoutError: The read operation timed out
```

during `sibyl init`, the CLI failed to reach **`https://api.sibyllabs.org/api/plugin/session-init`** within 10 seconds. Common causes:

1. **Firewall / VPN / corporate proxy** blocking or slowing HTTPS to `api.sibyllabs.org`
2. **Intermittent network** — retry on a different connection
3. **Antivirus SSL inspection** hanging the connection

**What to do:**

1. **Continue without activation** — start the server; Sibyl memory still works locally (`credentials_present: false` in `/health`).
2. **Test connectivity:**
   ```powershell
   curl -I https://api.sibyllabs.org
   ```
   You should get a response within a few seconds (403 is normal for bare requests).
3. **Retry** `sibyl init` on another network (mobile hotspot, no VPN).
4. **Check Windows Firewall** allows Python outbound HTTPS.

Activation is optional for hackathon/dev work. Re-run `sibyl init` later when connectivity is stable.

### Using Sibyl in code

Memory access is centralized in `app/services/memory.py`:

```python
from app.services.memory import get_memory_provider

# One SQLite DB per GitHub repo (tenant)
memory = get_memory_provider("my-org/my-repo")

# WARM — structured facts (decisions, architecture, constraints)
memory.remember("architecture", "database", {"choice": "PostgreSQL", "reason": "..."})

# Search across all tiers (FTS5, no embeddings)
hits = memory.search("PostgreSQL")

# Recall a specific entity
fact = memory.recall("architecture", "database")

# COLD — conversation / event journal
memory.save_context(
    inputs={"user": "Why PostgreSQL?"},
    outputs={"assistant": "Because..."},
)
```

| AI CTO concept | Sibyl tier | SDK method |
|----------------|------------|------------|
| Decisions, architecture | WARM entity | `remember()` / `recall()` |
| Incidents, changelog | COLD journal | `save_context()` |
| Session context | HOT state | `set_state()` |
| Docs / runbooks | REFERENCE | `set_reference()` |
| Retired knowledge | ARCHIVE | `archive()` |
| Search | FTS5 | `search()` |

Docs: [docs.sibyllabs.org/memory](https://docs.sibyllabs.org/memory/) · [Integrations (SDK)](https://docs.sibyllabs.org/memory/integrations)

### Production persistence

`SIBYL_DATA_DIR` must live on **persistent disk** that survives container restarts and redeploys. Do not use ephemeral filesystems for `./data/sibyl` in production.

## Project layout

```
server/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings (pydantic-settings)
│   ├── api/
│   │   ├── router.py
│   │   └── health.py        # GET /health
│   └── services/
│       └── memory.py        # Sibyl Memory wrapper
├── tests/
├── scripts/
│   ├── sibyl_simulation.py  # Compare CTO behavior with/without Sibyl
│   └── wipe_db.py           # Wipe PostgreSQL + optional Sibyl memory
├── data/sibyl/              # Local Sibyl SQLite (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

## Scripts

```powershell
# Run API with hot reload
uvicorn app.main:app --reload --port 8000

# Tests
pytest

# Sibyl CLI (optional, after pip install sibyl-memory-cli[mcp])
sibyl init
sibyl status
sibyl health
```

### Wipe database

**Destructive** — deletes all users, projects, chat history, tokens, and reports, then recreates empty tables. Uses `DATABASE_URL` from `.env`:

```env
DATABASE_URL=postgresql://user:password@host/neondb?sslmode=require
```

```powershell
# Preview (shows target, does not wipe)
python -m scripts.wipe_db

# Wipe PostgreSQL only
python -m scripts.wipe_db --yes

# Wipe PostgreSQL + local Sibyl memory (*.db under SIBYL_DATA_DIR)
python -m scripts.wipe_db --yes --sibyl
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Server + Sibyl memory status |

More routes (auth, chat, webhooks) are added as features land.

## Links

- [Sibyl Labs](https://sibyllabs.org/)
- [Sibyl Memory docs](https://docs.sibyllabs.org/memory/)
- [Sibyl Memory on GitHub](https://github.com/Sibyl-Labs/Sibyl-Memory)
