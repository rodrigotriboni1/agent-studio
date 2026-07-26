"""Pydantic request/response models for the chat API (V1-003 / V1-004).

Response envelopes mirror the FIXED ``chatContract`` in ``prd.json`` so the
frontend can build against them in parallel.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Domain wire-shapes (contract)
# ---------------------------------------------------------------------------


class ApprovalRequestModel(BaseModel):
    """chatContract ``ApprovalRequest`` { run_id, pending_step, resolved? }."""

    run_id: str
    pending_step: str | None = None
    resolved: Literal["approved", "rejected"] | None = None


class MessageModel(BaseModel):
    """chatContract ``Message`` — the shape returned for every turn."""

    role: Literal["user", "assistant", "system"]
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    denied: list[str] = Field(default_factory=list)
    approval: ApprovalRequestModel | None = None
    ts: str


class ConversationSummary(BaseModel):
    """A lightweight conversation (no messages) for the list endpoint."""

    id: str
    tenant_id: str
    agent_id: str | None = None
    title: str
    created_at: str


class ConversationModel(ConversationSummary):
    """A full conversation including its message history."""

    messages: list[MessageModel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Body for POST /agents/{id}/chat and .../chat/stream."""

    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    """Response for POST /agents/{id}/chat."""

    conversation_id: str
    message: MessageModel


class WorkflowChatRequest(BaseModel):
    """Body for POST /workflows/chat."""

    message: str
    definition: dict[str, Any]
    conversation_id: str | None = None


class WorkflowChatResponse(BaseModel):
    """Response for POST /workflows/chat."""

    conversation_id: str
    message: MessageModel


class ResumeRequest(BaseModel):
    """Body for POST /conversations/{id}/resume."""

    run_id: str
    approved: bool


class ResumeResponse(BaseModel):
    """Response for POST /conversations/{id}/resume."""

    conversation_id: str
    message: MessageModel


__all__ = [
    "ApprovalRequestModel",
    "ChatRequest",
    "ChatResponse",
    "ConversationModel",
    "ConversationSummary",
    "MessageModel",
    "ResumeRequest",
    "ResumeResponse",
    "WorkflowChatRequest",
    "WorkflowChatResponse",
]
