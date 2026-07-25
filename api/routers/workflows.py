"""Workflows router.

Endpoints:
  POST /workflows/run              start a workflow run
  POST /workflows/{run_id}/resume  resume a paused workflow (human-in-the-loop)
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from api.schemas import WorkflowResumeRequest, WorkflowRunRequest, WorkflowRunResponse
from api.services import AppState, get_app_state
from seams.tenancy import TenantContext

router = APIRouter(prefix="/workflows", tags=["workflows"])


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


@router.post("/run", response_model=WorkflowRunResponse)
def start_workflow(
    body: WorkflowRunRequest,
    tenant: TenantDep,
    state: StateDep,
) -> WorkflowRunResponse:
    run = state.workflow_engine.start(body.definition, body.inputs, tenant=tenant)
    return WorkflowRunResponse(
        id=run.id,
        state=run.state,
        output=run.output,
        pending_step=run.pending_step,
        history=run.history,
    )


@router.post("/{run_id}/resume", response_model=WorkflowRunResponse)
def resume_workflow(
    run_id: str,
    body: WorkflowResumeRequest,
    tenant: TenantDep,
    state: StateDep,
) -> WorkflowRunResponse:
    try:
        run = state.workflow_engine.resume(
            run_id, {"approved": body.approved}, tenant=tenant
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Workflow run {run_id!r} not found"
        ) from exc
    return WorkflowRunResponse(
        id=run.id,
        state=run.state,
        output=run.output,
        pending_step=run.pending_step,
        history=run.history,
    )
