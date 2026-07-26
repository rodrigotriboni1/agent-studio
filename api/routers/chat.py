"""Chat router (V1-003 + V1-004) — conversations, agent chat (+SSE) and
workflow-driven chat with human-in-the-loop resume.

Everything is tenant-scoped via the ``X-Tenant-Id`` header (default when absent),
threaded through ``use_tenant`` so deep seam calls read the right tenant. The
same :class:`~api.chat_store.ConversationStore` + ``Message`` shape backs both
the agent and the workflow paths (never duplicated).

SSE is implemented with a plain ``StreamingResponse`` (media type
``text/event-stream``) — NO new dependency. The offline echo output is split into
word tokens and streamed deterministically as ``{type:'token'}`` events, closing
with a ``{type:'done', message}`` event carrying citations/tool_calls/denied.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse

from api.chat_schemas import (
    ChatRequest,
    ChatResponse,
    ConversationModel,
    ConversationSummary,
    MessageModel,
    ResumeRequest,
    ResumeResponse,
    WorkflowChatRequest,
    WorkflowChatResponse,
)
from api.chat_store import ApprovalRequest, Conversation, Message
from api.services import AppState, get_app_state
from api.workflow_defs import normalize_workflow_definition
from core.manifest.schema import AgentManifest
from core.workflows import WorkflowRun, WorkflowState
from seams.tenancy import TenantContext, use_tenant

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# Dependencies (mirrors the existing routers' X-Tenant-Id handling)
# ---------------------------------------------------------------------------


def _resolve_tenant(x_tenant_id: Annotated[str | None, Header()] = None) -> TenantContext:
    tid = x_tenant_id or os.getenv("AGENT_STUDIO_DEFAULT_TENANT", "default")
    return TenantContext(tenant_id=tid)


TenantDep = Annotated[TenantContext, Depends(_resolve_tenant)]
StateDep = Annotated[AppState, Depends(get_app_state)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _message_model(msg: Message) -> MessageModel:
    return MessageModel.model_validate(msg.to_dict())


def _compose_with_history(manifest: AgentManifest, conversation: Conversation, message: str) -> str:
    """Prepend recent conversation turns (per ``manifest.memory.max_messages``)
    as context to the new user message.

    The runtime accepts a single message string; to feed prior history we build a
    transcript of the most recent ``max_messages`` turns (excluding the just-added
    user turn) and prepend it. Under the offline echo model this makes the prior
    turn visible in the assistant reply, so multi-turn context is observable.
    """
    max_messages = max(0, manifest.memory.max_messages)
    # Prior messages = everything before the current user turn we just appended.
    prior = conversation.messages[:-1] if conversation.messages else []
    if max_messages == 0 or not prior:
        return message
    recent = prior[-max_messages:]
    lines = [f"{m.role}: {m.content}" for m in recent]
    transcript = "\n".join(lines)
    return f"Conversation so far:\n{transcript}\n\nUser: {message}"


def _run_agent_turn(
    state: AppState,
    manifest: AgentManifest,
    conversation: Conversation,
    tenant: TenantContext,
    user_message: str,
) -> Message:
    """Run the agent with prior history and return the assistant Message.

    Governance denials from the run (tool-exposure or a model refusal) are
    surfaced on the returned assistant Message via ``denied``.
    """
    from core.runtime.agent import ModelAccessDenied

    composed = _compose_with_history(manifest, conversation, user_message)
    with use_tenant(tenant):
        try:
            result = state.runtime.run(manifest, composed, tenant=tenant)
            assistant = Message(
                role="assistant",
                content=result.output,
                citations=list(result.citations),
                tool_calls=list(result.tool_calls),
                denied=list(result.denied),
            )
        except ModelAccessDenied as exc:
            # A model refusal aborts the run; surface the denial on the message
            # instead of failing the whole chat turn.
            denied = list(exc.result.denied) if exc.result else [exc.reason]
            assistant = Message(
                role="assistant",
                content=f"Request denied by governance: {exc.reason}",
                denied=denied,
            )
    return assistant


def _load_manifest(state: AppState, tenant: TenantContext, agent_id: str) -> AgentManifest:
    try:
        return state.manifest_store.get(tenant.tenant_id, agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found") from exc


def _sse_event(payload: dict[str, Any]) -> str:
    """Format a single SSE ``data:`` frame."""
    return f"data: {json.dumps(payload)}\n\n"


# ---------------------------------------------------------------------------
# Agent chat
# ---------------------------------------------------------------------------


@router.post("/agents/{agent_id}/chat", response_model=ChatResponse)
def agent_chat(
    agent_id: str,
    body: ChatRequest,
    tenant: TenantDep,
    state: StateDep,
) -> ChatResponse:
    manifest = _load_manifest(state, tenant, agent_id)
    store = state.conversation_store

    conversation = store.get_or_create(
        tenant.tenant_id,
        body.conversation_id,
        agent_id=agent_id,
        title=body.message[:60] or "New conversation",
    )
    store.append(conversation, Message(role="user", content=body.message))
    assistant = _run_agent_turn(state, manifest, conversation, tenant, body.message)
    store.append(conversation, assistant)

    return ChatResponse(
        conversation_id=conversation.id,
        message=_message_model(assistant),
    )


@router.post("/agents/{agent_id}/chat/stream")
def agent_chat_stream(
    agent_id: str,
    body: ChatRequest,
    tenant: TenantDep,
    state: StateDep,
) -> StreamingResponse:
    manifest = _load_manifest(state, tenant, agent_id)
    store = state.conversation_store

    conversation = store.get_or_create(
        tenant.tenant_id,
        body.conversation_id,
        agent_id=agent_id,
        title=body.message[:60] or "New conversation",
    )
    store.append(conversation, Message(role="user", content=body.message))
    assistant = _run_agent_turn(state, manifest, conversation, tenant, body.message)
    store.append(conversation, assistant)

    def event_stream() -> Iterator[str]:
        # Deterministically split the assistant content into word tokens so the
        # offline echo streams in >=1 token event.
        text = assistant.content or ""
        tokens = text.split(" ") if text else []
        for i, tok in enumerate(tokens):
            # Preserve spacing between tokens (prefix every token but the first).
            chunk = tok if i == 0 else f" {tok}"
            yield _sse_event({"type": "token", "text": chunk})
        yield _sse_event(
            {"type": "done", "message": assistant.to_dict(), "conversation_id": conversation.id}
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Conversations (tenant-scoped)
# ---------------------------------------------------------------------------


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(tenant: TenantDep, state: StateDep) -> list[ConversationSummary]:
    convs = state.conversation_store.list(tenant.tenant_id)
    return [ConversationSummary.model_validate(c.to_dict(include_messages=False)) for c in convs]


@router.get("/conversations/{conversation_id}", response_model=ConversationModel)
def get_conversation(
    conversation_id: str,
    tenant: TenantDep,
    state: StateDep,
) -> ConversationModel:
    conv = state.conversation_store.get(tenant.tenant_id, conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=404, detail=f"Conversation {conversation_id!r} not found"
        )
    return ConversationModel.model_validate(conv.to_dict())


# ---------------------------------------------------------------------------
# Workflow-driven chat + resume (V1-004)
# ---------------------------------------------------------------------------


def _assistant_from_run(run: WorkflowRun) -> Message:
    """Turn a workflow run outcome into an assistant Message.

    A run paused at ``human_approval`` yields an assistant Message whose
    ``approval`` carries the ``run_id`` + ``pending_step``. A completed run yields
    the terminal output as content.
    """
    if run.state == WorkflowState.WAITING_APPROVAL:
        return Message(
            role="assistant",
            content=(
                f"Waiting for approval on step '{run.pending_step}'."
                if run.pending_step
                else "Waiting for approval."
            ),
            approval=ApprovalRequest(run_id=run.id, pending_step=run.pending_step),
        )
    content = run.output if isinstance(run.output, str) else json.dumps(run.output)
    return Message(role="assistant", content=content or "")


@router.post("/workflows/chat", response_model=WorkflowChatResponse)
def workflow_chat(
    body: WorkflowChatRequest,
    tenant: TenantDep,
    state: StateDep,
) -> WorkflowChatResponse:
    store = state.conversation_store
    conversation = store.get_or_create(
        tenant.tenant_id,
        body.conversation_id,
        title=body.message[:60] or "Workflow",
    )
    store.append(conversation, Message(role="user", content=body.message))

    with use_tenant(tenant):
        definition = normalize_workflow_definition(body.definition)
        run = state.workflow_engine.start(
            definition, {"message": body.message}, tenant=tenant
        )
    assistant = _assistant_from_run(run)
    store.append(conversation, assistant)

    return WorkflowChatResponse(
        conversation_id=conversation.id,
        message=_message_model(assistant),
    )


@router.post("/conversations/{conversation_id}/resume", response_model=ResumeResponse)
def resume_conversation(
    conversation_id: str,
    body: ResumeRequest,
    tenant: TenantDep,
    state: StateDep,
) -> ResumeResponse:
    store = state.conversation_store
    conversation = store.get(tenant.tenant_id, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=404, detail=f"Conversation {conversation_id!r} not found"
        )

    try:
        with use_tenant(tenant):
            run = state.workflow_engine.resume(
                body.run_id, {"approved": body.approved}, tenant=tenant
            )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Workflow run {body.run_id!r} not found"
        ) from exc

    # Mark the prior pending approval on this conversation as resolved.
    resolution = "approved" if body.approved else "rejected"
    for msg in reversed(conversation.messages):
        if msg.approval is not None and msg.approval.run_id == body.run_id:
            msg.approval.resolved = resolution
            break

    if body.approved:
        assistant = _assistant_from_run(run)
    else:
        # Rejected: prefer the workflow's terminal output, else a rejected note.
        content = run.output if isinstance(run.output, str) else None
        assistant = Message(
            role="assistant",
            content=content or "Workflow rejected.",
        )
    store.append(conversation, assistant)

    return ResumeResponse(
        conversation_id=conversation.id,
        message=_message_model(assistant),
    )
