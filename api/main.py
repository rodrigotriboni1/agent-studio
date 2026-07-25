"""FastAPI application factory.

v0 skeleton: health + version + seam wiring. Routers for agents CRUD, run,
ingest and workflows are mounted here (US-005).
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from seams import TenantContext

__version__ = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title="agent-studio",
        version=__version__,
        summary="Governed, multi-tenant, MCP-native builder for agents, RAG and workflows.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/version")
    def version() -> dict[str, str]:
        return {
            "version": __version__,
            "default_tenant": os.getenv("AGENT_STUDIO_DEFAULT_TENANT", "default"),
            "offline": os.getenv("AGENT_STUDIO_OFFLINE", "0"),
        }

    # Mount routers (US-005)
    from api.routers import agents, ingest, runs, workflows

    app.include_router(agents.router)
    app.include_router(runs.router)
    app.include_router(ingest.router)
    app.include_router(workflows.router)

    _ = TenantContext  # keep the seam import meaningful for wiring
    return app


app = create_app()
