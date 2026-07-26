"""FastAPI application factory.

v0 skeleton: health + version + seam wiring. Routers for agents CRUD, run,
ingest and workflows are mounted here (US-005). v1 adds CORS + the chat router
(conversations, agent chat with SSE, workflow-driven chat) — see api/routers/chat.py.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import Settings, get_settings
from seams import TenantContext

__version__ = "0.1.0"


def _db_health(settings: Settings) -> str:
    """Return 'skipped' when no DATABASE_URL, else a best-effort 'up'/'down'.

    Offline-first: when offline (no network) we never dial the DB, so a
    configured-but-unreachable URL simply reports 'down' without raising.
    """
    if not settings.database_url:
        return "skipped"
    if settings.offline:
        return "down"
    try:
        import psycopg  # lazy, optional

        with psycopg.connect(settings.database_url, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return "up"
    except Exception:
        return "down"


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="agent-studio",
        version=__version__,
        summary="Governed, multi-tenant, MCP-native builder for agents, RAG and workflows.",
    )

    # CORS (V1-002): allow the configured browser origins with credentials and
    # every method/header (incl. X-Tenant-Id) so the SPA can call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        # db is 'skipped' when no DATABASE_URL is configured (offline default),
        # otherwise a best-effort connectivity probe reports 'up' or 'down'.
        return {"status": "ok", "db": _db_health(settings)}

    @app.get("/version")
    def version() -> dict[str, str]:
        return {
            "version": __version__,
            "default_tenant": os.getenv("AGENT_STUDIO_DEFAULT_TENANT", "default"),
            "offline": os.getenv("AGENT_STUDIO_OFFLINE", "0"),
        }

    # Mount routers (US-005 + v1 chat)
    from api.routers import agents, chat, ingest, runs, workflows

    app.include_router(agents.router)
    app.include_router(runs.router)
    app.include_router(ingest.router)
    app.include_router(workflows.router)
    app.include_router(chat.router)

    _ = TenantContext  # keep the seam import meaningful for wiring
    return app


app = create_app()
