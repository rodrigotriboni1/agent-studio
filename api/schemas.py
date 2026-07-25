"""Pydantic request/response models for the API layer.

Kept separate from core schemas so the API surface can evolve independently
of the internal domain models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Agent CRUD
# ---------------------------------------------------------------------------


class CreateAgentRequest(BaseModel):
    """Body for POST /agents."""

    name: str
    description: str = ""
    system_prompt: str = "You are a helpful assistant."
    model: str = "echo"
    allowed_models: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateAgentRequest(BaseModel):
    """Body for PUT /agents/{id} — partial update (only provided fields change)."""

    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    allowed_models: list[str] | None = None
    allowed_tools: list[str] | None = None
    metadata: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    """Single-agent response envelope."""

    id: str
    tenant_id: str
    name: str
    description: str
    version: int
    status: str
    system_prompt: str
    model: str
    allowed_models: list[str]
    allowed_tools: list[str]
    metadata: dict[str, Any]


class RollbackRequest(BaseModel):
    target_version: int


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    message: str


class RunResponse(BaseModel):
    output: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    denied: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class IngestDocument(BaseModel):
    id: str
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[IngestDocument]


class IngestResponse(BaseModel):
    chunks: int


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


class WorkflowRunRequest(BaseModel):
    definition: dict[str, Any]
    inputs: dict[str, Any] = Field(default_factory=dict)


class WorkflowResumeRequest(BaseModel):
    approved: bool


class WorkflowRunResponse(BaseModel):
    id: str
    state: str
    output: Any = None
    pending_step: str | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
