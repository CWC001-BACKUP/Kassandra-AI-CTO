# Kassandra client

React + TypeScript + Vite dashboard for Kassandra (AI CTO).

Product overview / Sibyl hackathon docs: **[../README.md](../README.md)**  
Server API (Scalar): **[http://localhost:8000/scalar](http://localhost:8000/scalar)** when the backend is running.

## Quick start

```powershell
cd client
npm install
npm run dev
```

App: [http://localhost:5173](http://localhost:5173)

Vite proxies `/api` → `http://localhost:8000` (see [`vite.config.ts`](vite.config.ts)).

## Key UI surfaces

| Page | Path | Role |
|------|------|------|
| Chat | [`src/pages/dashboard/ChatPage.tsx`](src/pages/dashboard/ChatPage.tsx) | CTO chat + **Sibyl on/off** toggle (`sibyl_enabled`) |
| Teach | [`src/pages/dashboard/TeachPage.tsx`](src/pages/dashboard/TeachPage.tsx) | Knowledge gaps + confirm institutional facts |
| Projects | [`src/pages/dashboard/ProjectsPage.tsx`](src/pages/dashboard/ProjectsPage.tsx) | Connect / activate GitHub repos |

## Scripts

```powershell
npm run dev      # Vite HMR on :5173
npm run build    # production build
npm run lint     # oxlint
npm run preview  # preview production build
```
