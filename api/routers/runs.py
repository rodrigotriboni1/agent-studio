"""Runs router.

Endpoints:
  POST /agents/{id}/run   run an agent with a single message

Governance denials (ModelAccessDenied) are surfaced as HTTP 403 with the
denial details in the response body (JSON ``{"detail": {"denied": [...], "reason": "..."}}``.
The ``denied`` list from RunResult is always propagated so callers can see
exactly which resource was blocked and why.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from api.schemas import RunRequest, RunResponse
from api.services import AppState, get_app_state
from seams.tenancy import TenantContext

router = APIRouter(tags=["runs"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_tenant(x_tenant_id: Annotated[str | None, Header()] = None) -> TenantContext:
    tid = x_tenant_id or os.getenv("AGENT_STUDIO_DEFAULT_TENANT", "default")
    return TenantContext(tenant_id=tid)


TenantDep = Annotated[TenantContext, Depends(_resolve_tenant)]
StateDep = Annotated[AppState, Depends(get_app_state)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/agents/{agent_id}/run", response_model=RunResponse)
def run_agent(
    agent_id: str,
    body: RunRequest,
    tenant: TenantDep,
    state: StateDep,
) -> RunResponse:
    try:
        manifest = state.manifest_store.get(tenant.tenant_id, agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found") from exc

    # Guard against ModelAccessDenied so governance denials are always visible.
    from core.runtime.agent import ModelAccessDenied

    try:
        result = state.runtime.run(manifest, body.message, tenant=tenant)
        return RunResponse(
            output=result.output,
            tool_calls=result.tool_calls,
            citations=result.citations,
            denied=result.denied,
        )
    except ModelAccessDenied as exc:
        # The denial is surfaced as HTTP 403; denied list comes from exc.result.
        denied_list = exc.result.denied if exc.result else [str(exc)]
        raise HTTPException(
            status_code=403,
            detail={"denied": denied_list, "reason": exc.reason},
        ) from exc
