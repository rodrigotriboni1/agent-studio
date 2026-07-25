"""Ingest router.

Endpoints:
  POST /sources/{name}/ingest   ingest a list of documents into a named RAG source
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from api.schemas import IngestRequest, IngestResponse
from api.services import AppState, get_app_state
from core.rag import Document
from seams.tenancy import TenantContext

router = APIRouter(prefix="/sources", tags=["ingest"])


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


@router.post("/{name}/ingest", response_model=IngestResponse)
def ingest_source(
    name: str,
    body: IngestRequest,
    tenant: TenantDep,
    state: StateDep,
) -> IngestResponse:
    documents = [
        Document(id=doc.id, text=doc.text, metadata=doc.metadata)
        for doc in body.documents
    ]
    chunks = state.rag_index.ingest(name, documents, tenant=tenant)
    return IngestResponse(chunks=chunks)
