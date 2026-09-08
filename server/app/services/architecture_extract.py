"""Extract OBSERVED architecture facts from repository manifests and structure."""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.institutional_memory import (
    SOURCE_ANALYSIS,
    SOURCE_DOCS,
    build_memory,
)

# dependency name → (layer, display label)
_DEP_MAP: dict[str, tuple[str, str]] = {
    "next": ("frontend", "Next.js"),
    "react": ("frontend", "React"),
    "vue": ("frontend", "Vue"),
    "nuxt": ("frontend", "Nuxt"),
    "svelte": ("frontend", "Svelte"),
    "@angular/core": ("frontend", "Angular"),
    "express": ("backend", "Express"),
    "fastify": ("backend", "Fastify"),
    "nestjs": ("backend", "NestJS"),
    "@nestjs/core": ("backend", "NestJS"),
    "koa": ("backend", "Koa"),
    "hapi": ("backend", "Hapi"),
    "fastapi": ("backend", "FastAPI"),
    "django": ("backend", "Django"),
    "flask": ("backend", "Flask"),
    "prisma": ("database", "Prisma"),
    "@prisma/client": ("database", "Prisma"),
    "typeorm": ("database", "TypeORM"),
    "sequelize": ("database", "Sequelize"),
    "mongoose": ("database", "Mongoose / MongoDB"),
    "pg": ("database", "PostgreSQL (pg)"),
    "postgres": ("database", "PostgreSQL"),
    "mysql": ("database", "MySQL"),
    "mongodb": ("database", "MongoDB"),
    "redis": ("database", "Redis"),
    "sqlite3": ("database", "SQLite"),
    "sqlalchemy": ("database", "SQLAlchemy"),
    "jsonwebtoken": ("authentication", "JWT"),
    "passport": ("authentication", "Passport"),
    "next-auth": ("authentication", "NextAuth"),
    "@auth0/nextjs-auth0": ("authentication", "Auth0"),
    "jest": ("testing", "Jest"),
    "vitest": ("testing", "Vitest"),
    "playwright": ("testing", "Playwright"),
    "@playwright/test": ("testing", "Playwright"),
    "cypress": ("testing", "Cypress"),
    "pytest": ("testing", "pytest"),
    "docker": ("infrastructure", "Docker"),
    "graphql": ("api", "GraphQL"),
    "@apollo/client": ("api", "Apollo GraphQL"),
    "trpc": ("api", "tRPC"),
    "@trpc/server": ("api", "tRPC"),
}

_HISTORY_SIGNALS = (
    (r"\bmigrat(?:e|ed|ion)\b", "migration"),
    (r"\brefact(?:or|ored|oring)\b", "refactor"),
    (r"\breplace[sd]?\b.*\b(mongo|postgres|mysql|redis|auth|api)\b", "replacement"),
    (r"\b(switch|moved|move)\b.*\b(to|from)\b", "technology_shift"),
    (r"\bauth(?:entication|oriz)?\b", "authentication_change"),
    (r"\b(security|cve|vulnerabilit)\b", "security_change"),
    (r"\b(perf(?:ormance)?|optimiz|latency|throughput)\b", "performance_change"),
    (r"\b(database|schema|prisma|sql)\b", "database_change"),
    (r"\b(breaking|deprecat)\b", "breaking_change"),
    (r"\b(delete|remov(?:e|ed|al)|legacy)\b", "removal"),
)


def _collect_js_deps(package_json: str) -> set[str]:
    try:
        data = json.loads(package_json)
    except json.JSONDecodeError:
        return set()
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = data.get(key) or {}
        if isinstance(section, dict):
            deps.update(str(k).lower() for k in section)
    return deps


def _collect_py_deps(text: str) -> set[str]:
    deps: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        # requirements.txt / simple pyproject dependency lines
        name = re.split(r"[<>=!~\s;\[]", line, maxsplit=1)[0].strip().lower()
        name = name.replace("_", "-")
        if name:
            deps.add(name)
            deps.add(name.replace("-", "_"))
    # pyproject poetry-style
    for match in re.finditer(
        r'^\s*["\']?([a-zA-Z0-9_-]+)["\']?\s*=',
        text,
        re.MULTILINE,
    ):
        deps.add(match.group(1).lower())
    return deps


def extract_stack_from_manifests(
    config_snippets: dict[str, str],
    *,
    root_files: list[str],
    languages: dict[str, int],
    readme: str | None,
) -> dict[str, list[str]]:
    """Build layered stack map from repository evidence only."""
    layers: dict[str, list[str]] = {
        "frontend": [],
        "backend": [],
        "database": [],
        "api": [],
        "authentication": [],
        "infrastructure": [],
        "testing": [],
        "languages": [],
    }

    def add(layer: str, label: str) -> None:
        if label not in layers[layer]:
            layers[layer].append(label)

    deps: set[str] = set()
    if "package.json" in config_snippets:
        deps |= _collect_js_deps(config_snippets["package.json"])
    for py_file in ("requirements.txt", "pyproject.toml"):
        if py_file in config_snippets:
            deps |= _collect_py_deps(config_snippets[py_file])

    for dep, (layer, label) in _DEP_MAP.items():
        if dep.lower() in deps:
            add(layer, label)

    # Language evidence from GitHub languages API
    for lang in languages:
        add("languages", lang)

    root_lower = {f.lower() for f in root_files}
    if "dockerfile" in root_lower or "docker-compose.yml" in root_lower:
        add("infrastructure", "Docker")
    if any(f.startswith(".github/workflows") or f == ".github" for f in root_files):
        add("infrastructure", "GitHub Actions")
    # shallow: workflows often not in root listing — check config keys
    if any("workflow" in k.lower() for k in config_snippets):
        add("infrastructure", "GitHub Actions")

    if "go.mod" in root_lower:
        add("backend", "Go")
    if "cargo.toml" in root_lower:
        add("backend", "Rust")
    if "pom.xml" in root_lower or "build.gradle" in root_lower:
        add("backend", "Java")

    # README hints (observed documentation, still marked as documentation source)
    if readme:
        lower = readme.lower()
        if "rest" in lower and "api" in lower:
            add("api", "REST")
        if "graphql" in lower:
            add("api", "GraphQL")
        if "jwt" in lower:
            add("authentication", "JWT")

    # Infer REST only when Express/FastAPI/Flask present without GraphQL
    if not layers["api"]:
        if any(x in layers["backend"] for x in ("Express", "FastAPI", "Flask", "Django", "NestJS")):
            add("api", "REST")

    return {k: v for k, v in layers.items() if v}


def architecture_memories_from_stack(
    stack: dict[str, list[str]],
    *,
    project_id: str | None,
    repo_full_name: str,
) -> list[dict[str, Any]]:
    memories: list[dict[str, Any]] = []
    for layer, items in stack.items():
        if not items:
            continue
        label = layer.replace("_", " ").title()
        memories.append(
            build_memory(
                memory_type="observation",
                title=f"{label}: {', '.join(items)}",
                content=f"Repository evidence indicates {label.lower()}: {', '.join(items)}.",
                decision=None,
                reason=None,
                source=SOURCE_ANALYSIS,
                source_reference=repo_full_name,
                confidence="observed",
                project_id=project_id,
                affected_components=[layer],
                tags=["architecture", layer],
            )
        )
    return memories


def is_meaningful_commit_message(message: str) -> bool:
    lower = message.lower()
    return any(re.search(pat, lower) for pat, _ in _HISTORY_SIGNALS)


def classify_commit_signal(message: str) -> str | None:
    lower = message.lower()
    for pat, label in _HISTORY_SIGNALS:
        if re.search(pat, lower):
            return label
    return None


def history_memory_from_commit(
    commit: dict[str, Any],
    *,
    project_id: str | None,
    signal: str,
) -> dict[str, Any]:
    title = commit.get("title") or commit.get("message") or "Significant commit"
    sha = commit.get("sha") or commit.get("id") or ""
    return build_memory(
        memory_type="historical_event",
        title=title[:120],
        content=f"Meaningful historical signal ({signal.replace('_', ' ')}) observed in git history.",
        decision=title[:200],
        reason=None,  # WHY usually unknown from commit message alone
        source=SOURCE_COMMIT,
        source_reference=sha[:12] if sha else None,
        confidence="observed",
        project_id=project_id,
        historical_date=commit.get("date") or commit.get("timestamp"),
        related_commits=[sha] if sha else [],
        tags=["git_history", signal],
    )


def inference_from_history(
    commits: list[dict[str, Any]],
    *,
    project_id: str | None,
) -> list[dict[str, Any]]:
    """Light inferences from patterns — always labeled inferred, never promoted to fact."""
    titles = " ".join((c.get("title") or "").lower() for c in commits)
    inferences: list[dict[str, Any]] = []

    if re.search(r"mongo", titles) and re.search(r"postgres|postgresql|prisma", titles):
        inferences.append(
            build_memory(
                memory_type="inference",
                title="Possible database migration involving MongoDB and PostgreSQL",
                content=(
                    "Commit history mentions both MongoDB and PostgreSQL/Prisma. "
                    "This suggests a database migration, but the reason is not established."
                ),
                decision="Database may have migrated between MongoDB and PostgreSQL",
                reason=None,
                source="system_inference",
                confidence="inferred",
                project_id=project_id,
                affected_components=["database"],
                tags=["git_history", "migration"],
            )
        )

    if re.search(r"auth", titles) and re.search(r"refactor|redesign|rework|rewrite", titles):
        inferences.append(
            build_memory(
                memory_type="inference",
                title="Authentication appears to have been redesigned",
                content=(
                    "Commit history suggests authentication was refactored or redesigned. "
                    "The business reason is unknown without developer confirmation."
                ),
                decision="Authentication redesign may have occurred",
                source="system_inference",
                confidence="inferred",
                project_id=project_id,
                affected_components=["authentication"],
                tags=["git_history", "authentication"],
            )
        )

    return inferences


def documentation_memory(readme: str | None, *, project_id: str | None, repo: str) -> dict[str, Any] | None:
    if not readme or len(readme.strip()) < 40:
        return None
    snippet = readme.strip().splitlines()[0][:200]
    return build_memory(
        memory_type="observation",
        title="README documentation present",
        content=f"Repository includes a README. Opening: {snippet}",
        source=SOURCE_DOCS,
        source_reference=f"{repo}/README",
        confidence="observed",
        project_id=project_id,
        tags=["documentation"],
    )
