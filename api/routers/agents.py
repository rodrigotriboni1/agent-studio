"""Agents CRUD router.

Endpoints:
  POST   /agents                     create draft
  GET    /agents                     list latest versions for tenant
  GET    /agents/{id}                get latest version
  PUT    /agents/{id}                edit draft (creates a new draft version)
  POST   /agents/{id}/publish        publish draft → immutable published version
  GET    /agents/{id}/versions       full version history
  POST   /agents/{id}/rollback       rollback to a prior version
"""

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

from api.schemas import (
    AgentResponse,
    CreateAgentRequest,
    RollbackRequest,
    UpdateAgentRequest,
)
from api.services import AppState, get_app_state
from core.manifest.schema import AgentManifest
from core.manifest.versioning import publish, rollback
from seams.tenancy import TenantContext

router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_tenant(x_tenant_id: Annotated[str | None, Header()] = None) -> TenantContext:
    """Resolve TenantContext from the X-Tenant-Id header (default when absent)."""
    tid = x_tenant_id or os.getenv("AGENT_STUDIO_DEFAULT_TENANT", "default")
    return TenantContext(tenant_id=tid)


def _manifest_to_response(m: AgentManifest) -> AgentResponse:
    return AgentResponse(
        id=m.id,
        tenant_id=m.tenant_id,
        name=m.name,
        description=m.description,
        version=m.version,
        status=m.status,
        system_prompt=m.system_prompt,
        model=m.model,
        allowed_models=m.allowed_models,
        allowed_tools=m.allowed_tools,
        metadata=m.metadata,
    )


# Type aliases for dependency injection
TenantDep = Annotated[TenantContext, Depends(_resolve_tenant)]
StateDep = Annotated[AppState, Depends(get_app_state)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=AgentResponse, status_code=201)
def create_agent(
    body: CreateAgentRequest,
    tenant: TenantDep,
    state: StateDep,
) -> AgentResponse:
    agent_id = str(uuid.uuid4())
    manifest = AgentManifest(
        id=agent_id,
        tenant_id=tenant.tenant_id,
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        model=body.model,
        allowed_models=body.allowed_models,
        allowed_tools=body.allowed_tools,
        metadata=body.metadata,
        version=1,
    )
    state.manifest_store.save(manifest)
    return _manifest_to_response(manifest)


@router.get("", response_model=list[AgentResponse])
def list_agents(tenant: TenantDep, state: StateDep) -> list[AgentResponse]:
    manifests = state.manifest_store.list(tenant.tenant_id)
    return [_manifest_to_response(m) for m in manifests]


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str, tenant: TenantDep, state: StateDep) -> AgentResponse:
    try:
        m = state.manifest_store.get(tenant.tenant_id, agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found") from exc
    return _manifest_to_response(m)


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    body: UpdateAgentRequest,
    tenant: TenantDep,
    state: StateDep,
) -> AgentResponse:
    try:
        current = state.manifest_store.get(tenant.tenant_id, agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found") from exc

    # Build an updated draft.  If the current latest version is already
    # published (immutable), we create a new draft at the next version slot so
    # the published record is never mutated.
    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.system_prompt is not None:
        updates["system_prompt"] = body.system_prompt
    if body.model is not None:
        updates["model"] = body.model
    if body.allowed_models is not None:
        updates["allowed_models"] = body.allowed_models
    if body.allowed_tools is not None:
        updates["allowed_tools"] = body.allowed_tools
    if body.metadata is not None:
        updates["metadata"] = body.metadata

    from core.manifest.schema import ManifestStatus

    if current.is_published():
        # Published manifests are immutable — allocate a fresh draft version.
        history = state.manifest_store.history(tenant.tenant_id, agent_id)
        next_v = (max(m.version for m in history) + 1) if history else 1
        updates.setdefault("status", ManifestStatus.DRAFT)
        updates["version"] = next_v
    else:
        # Still a draft — update in-place (same version key).
        updates.setdefault("status", ManifestStatus.DRAFT)

    updated = current.model_copy(update=updates)
    state.manifest_store.save(updated)
    return _manifest_to_response(updated)


@router.post("/{agent_id}/publish", response_model=AgentResponse)
def publish_agent(agent_id: str, tenant: TenantDep, state: StateDep) -> AgentResponse:
    try:
        current = state.manifest_store.get(tenant.tenant_id, agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found") from exc
    published = publish(state.manifest_store, current)
    return _manifest_to_response(published)


@router.get("/{agent_id}/versions", response_model=list[AgentResponse])
def get_versions(agent_id: str, tenant: TenantDep, state: StateDep) -> list[AgentResponse]:
    history = state.manifest_store.history(tenant.tenant_id, agent_id)
    return [_manifest_to_response(m) for m in history]


@router.post("/{agent_id}/rollback", response_model=AgentResponse)
def rollback_agent(
    agent_id: str,
    body: RollbackRequest,
    tenant: TenantDep,
    state: StateDep,
) -> AgentResponse:
    try:
        rolled = rollback(state.manifest_store, tenant.tenant_id, agent_id, body.target_version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _manifest_to_response(rolled)
