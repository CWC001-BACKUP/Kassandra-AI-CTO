# Kassandra — AI CTO with load-bearing Sibyl Memory

> **NOTE:** For the duration of hackathon testing and judging, keys and related config are left in `.env` / `.env.example` so judges can get straight into testing. They will be deactivated afterwards.

**Kassandra** is an AI CTO for engineering teams: connect a GitHub repository, ask what changed and *why* decisions were made, teach institutional context, and get answers grounded in **GitHub evidence** plus **persisted Sibyl Memory** that survives across sessions.

Public repo: [github.com/CWC001-BACKUP/Kassandra-AI-CTO](https://github.com/CWC001-BACKUP/Kassandra-AI-CTO)  
License: [Apache-2.0](./LICENSE)  
Hackathon: [Sibyl Labs Hackathon](https://hack.sibyllabs.org/) · [Rules](https://hack.sibyllabs.org/rules)

---

## What it does

1. **Connect a GitHub repo** — OAuth + project activation.
2. **Bootstrap understanding** — infer architecture/facts from the repo; surface knowledge gaps.
3. **Chat as AI CTO** — commit facts from GitHub; institutional *why* from Sibyl.
4. **Teach → confirm → store** — candidate memories are never silently written; the developer confirms first.
5. **Fresh-session recall** — open a new chat; Kassandra retrieves confirmed Sibyl memories and changes the answer.

Toggle **Sibyl** off in chat to run GitHub-only mode. Institutional recall and teach-to-memory degrade or stop — that is the load-bearing litmus test.

---

## Where Sibyl Memory is load-bearing

Delete / disable the Sibyl layer and the **core AI-CTO claim** (institutional why, taught policies, cross-session recall) fails or materially degrades. GitHub commit Q&A can still answer surface facts — that is intentional evidence separation, not decorative memory.

| Concern | Path | Role |
|---------|------|------|
| Sibyl SDK wrapper (per-repo SQLite tenants) | [`server/app/services/memory.py`](server/app/services/memory.py) | `get_memory_provider()` → `remember` / `search` / `recall` |
| Structured institutional memories + gaps | [`server/app/services/institutional_memory.py`](server/app/services/institutional_memory.py) | Confirmed facts, confidence, understanding report |
| Pending confirmation (write gate) | [`server/app/services/pending_memory.py`](server/app/services/pending_memory.py) | Extract → pending → yes/no/select → persist |
| Teach API orchestration | [`server/app/services/teach.py`](server/app/services/teach.py) | Teach Kassandra + confirm into Sibyl |
| Chat critical path (`sibyl_enabled`) | [`server/app/services/chat.py`](server/app/services/chat.py) | Search memory, inject context, skip teach when off |
| Evidence provenance (`github` / `sibyl` / `session`) | [`server/app/services/evidence.py`](server/app/services/evidence.py) | Distinct Sibyl evidence in UI |
| Teach / understanding HTTP API | [`server/app/api/projects.py`](server/app/api/projects.py) | `/projects/.../teach`, `/understanding`, `/memory/*` |
| Chat HTTP + `sibyl_enabled` body flag | [`server/app/api/chat.py`](server/app/api/chat.py) | `POST /chat` |
| UI Sibyl toggle | [`client/src/pages/dashboard/ChatPage.tsx`](client/src/pages/dashboard/ChatPage.tsx) | Local preference → API |
| Teach UI | [`client/src/pages/dashboard/TeachPage.tsx`](client/src/pages/dashboard/TeachPage.tsx) | Gaps + confirm facts |
| On-disk memory | `server/data/sibyl/*.db` | One SQLite DB per `owner__repo` tenant |

### How memory made this possible

Without Sibyl, Kassandra is a GitHub-aware chatbot. With Sibyl, a developer can **teach** a constraint (e.g. “new developers must not run live EC2 isolation unlock without senior review”), **confirm** it, close the session, open a **fresh** chat, and ask what is dangerous for new developers — the answer changes because of persisted institutional memory, not because the chat history was reloaded.

### Demo beat (fresh-session recall)

1. Sibyl **On**. Active project: a connected GitHub repo.
2. Teach a decision/constraint in chat or Teach page → reply **yes** to save.
3. Start a **new** chat session (empty history).
4. Ask for that decision — Kassandra recalls it from Sibyl with Sibyl evidence chips.
5. Optional: toggle Sibyl **Off** and ask again — institutional answer collapses; GitHub facts still work.

---

## Partner stacks

| Stack | Used? | Notes |
|-------|-------|-------|
| **Sibyl Memory** | **Required / yes** | Load-bearing institutional memory (not a bonus stack) |
| Base | No | Not claimed |
| Virtuals Protocol | No | Not claimed |

Multiplier: **x1.00** (Sibyl only).

---

## Prior Work declaration

- **Kassandra (this repo)** was built as an AI CTO product integrating GitHub + Sibyl Memory for the Sibyl Labs Hackathon build window.
- **Prior / dependency work (not claimed as the submission invention):** FastAPI, React/Vite, PostgreSQL (Neon), GitHub OAuth API, OpenAI-compatible LLM APIs, and the open-source [Sibyl Memory](https://github.com/Sibyl-Labs/Sibyl-Memory) SDK (`sibyl-memory-hermes`).
- No Sibyl Labs staff reference build is reused as the product core. Institutional memory schema, pending confirmation, evidence separation, and Teach flow are original to this project.

---

## Repository layout

```
Kassandra-AI-CTO/
├── LICENSE                 # Apache-2.0
├── README.md               # This file (hackathon + product overview)
├── client/                 # React + Vite dashboard (port 5173)
│   ├── src/pages/dashboard/ChatPage.tsx
│   ├── src/pages/dashboard/TeachPage.tsx
│   └── vite.config.ts      # Proxies /api → http://localhost:8000
└── server/                 # FastAPI backend (port 8000)
    ├── README.md           # Server deep-dive + API docs
    ├── requirements.txt
    ├── .env.example
    ├── app/
    │   ├── main.py         # App + Scalar docs at /scalar
    │   ├── api/            # HTTP routes
    │   └── services/       # Chat, Sibyl, GitHub, teach, …
    ├── data/sibyl/         # Local Sibyl SQLite (gitignored)
    ├── scripts/            # feature_scenario, wipe_db, …
    └── tests/
```

---

## Installation & startup

### Prerequisites

- Python **3.10+**
- Node.js **20+** (client)
- PostgreSQL (e.g. [Neon](https://neon.tech))
- GitHub OAuth app
- OpenAI-compatible LLM key

### 1. Server

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env: DATABASE_URL, JWT_SECRET, GitHub OAuth, LLM_*, optional Sibyl paths

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Purpose |
|-----|---------|
| [http://localhost:8000/health](http://localhost:8000/health) | Health + Sibyl status |
| [http://localhost:8000/scalar](http://localhost:8000/scalar) | **Scalar** interactive API docs |
| [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI (FastAPI default) |
| [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) | OpenAPI schema |

Full server docs: [`server/README.md`](server/README.md).

### 2. Client

```powershell
cd client
npm install
npm run dev
```

App: [http://localhost:5173](http://localhost:5173)  
Vite proxies `/api/*` → `http://localhost:8000/*`.

### 3. Sibyl Memory (local-first)

No `SIBYL_API_KEY`. Memory is **SQLite on disk** under `SIBYL_DATA_DIR` (default `server/data/sibyl/`).

```powershell
# Optional account activation (lifts free-tier caps)
pip install 'sibyl-memory-cli[mcp]'
sibyl init
sibyl status
```

Unactivated local mode is enough for hackathon demos. See [Sibyl Memory docs](https://docs.sibyllabs.org/memory/) and [`server/README.md`](server/README.md#sibyl-memory).

---

## Key HTTP surfaces (memory-critical)

| Method | Path | Why it matters |
|--------|------|----------------|
| `POST` | `/chat` | Chat; body includes `sibyl_enabled` |
| `POST` | `/projects/{id}/teach` | Teach / confirm into Sibyl |
| `POST` | `/memory/teach` | Teach against active project |
| `POST` | `/memory/confirm` | Confirm pending memories |
| `GET` | `/projects/{id}/understanding` | What Sibyl knows / gaps |
| `GET` | `/memory/search` | Search institutional memory |
| `POST` | `/projects/{id}/memories/{id}/review` | Confirm / reject / correct a fact |
| `GET` | `/health` | `sibyl.ready`, `credentials_present` |

Browse and try these in **Scalar**: [http://localhost:8000/scalar](http://localhost:8000/scalar).

---

## Environment (summary)

Copy [`server/.env.example`](server/.env.example) → `server/.env`.

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL (app users, sessions, projects) |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth |
| `GITHUB_REDIRECT_URI` | Default `http://localhost:8000/auth/github/callback` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | LLM provider |
| `SIBYL_DATA_DIR` | Local Sibyl SQLite directory |
| `SIBYL_CREDENTIALS` | Optional activation file (`~/.sibyl-memory/credentials.json`) |
| `FRONTEND_URL` | Default `http://localhost:5173` |

---

## Links

| Resource | URL |
|----------|-----|
| This repository | https://github.com/CWC001-BACKUP/Kassandra-AI-CTO |
| Sibyl Labs | https://sibyllabs.org/ |
| Sibyl Memory docs | https://docs.sibyllabs.org/memory/ |
| Sibyl Memory GitHub | https://github.com/Sibyl-Labs/Sibyl-Memory |
| Hackathon | https://hack.sibyllabs.org/ |
| Hackathon rules | https://hack.sibyllabs.org/rules |
| Scalar (API reference) | https://scalar.com/ |
