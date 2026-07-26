"""Tenant-scoped conversation store (V1-003 / V1-004).

Implements the FIXED ``chatContract`` domain objects:

    Conversation  { id, tenant_id, agent_id?, title, created_at, messages[] }
    Message       { role, content, citations?, tool_calls?, denied?, approval?, ts }
    ApprovalRequest { run_id, pending_step, resolved?: 'approved'|'rejected' }

In-memory and deliberately simple: a dict keyed by ``(tenant_id, conversation_id)``
so conversations are never visible across tenants. A single instance lives on the
``AppState`` singleton (see ``api/services.py``).
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant", "system"]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


@dataclass
class ApprovalRequest:
    """A pending human-approval interrupt raised by a workflow-driven turn."""

    run_id: str
    pending_step: str | None = None
    resolved: Literal["approved", "rejected"] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "pending_step": self.pending_step,
            "resolved": self.resolved,
        }


@dataclass
class Message:
    """A single chat message. Mirrors the chatContract ``Message`` shape."""

    role: Role
    content: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)
    approval: ApprovalRequest | None = None
    ts: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "citations": self.citations,
            "tool_calls": self.tool_calls,
            "denied": self.denied,
            "approval": self.approval.to_dict() if self.approval else None,
            "ts": self.ts,
        }


@dataclass
class Conversation:
    """A tenant-scoped conversation with its ordered message history."""

    id: str
    tenant_id: str
    agent_id: str | None = None
    title: str = "New conversation"
    created_at: str = field(default_factory=_now_iso)
    messages: list[Message] = field(default_factory=list)

    def to_dict(self, *, include_messages: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "title": self.title,
            "created_at": self.created_at,
        }
        if include_messages:
            data["messages"] = [m.to_dict() for m in self.messages]
        return data


class ConversationStore:
    """In-memory, tenant-scoped conversation store.

    Keyed by ``(tenant_id, conversation_id)`` so a conversation created for one
    tenant is never returned to another.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], Conversation] = {}

    # -- creation / lookup -------------------------------------------------

    def create(
        self,
        tenant_id: str,
        *,
        agent_id: str | None = None,
        title: str | None = None,
    ) -> Conversation:
        conv = Conversation(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            agent_id=agent_id,
            title=title or "New conversation",
        )
        self._by_key[(tenant_id, conv.id)] = conv
        return conv

    def get(self, tenant_id: str, conversation_id: str) -> Conversation | None:
        return self._by_key.get((tenant_id, conversation_id))

    def get_or_create(
        self,
        tenant_id: str,
        conversation_id: str | None,
        *,
        agent_id: str | None = None,
        title: str | None = None,
    ) -> Conversation:
        """Return the identified conversation (tenant-scoped) or create a fresh one."""
        if conversation_id:
            existing = self.get(tenant_id, conversation_id)
            if existing is not None:
                return existing
        return self.create(tenant_id, agent_id=agent_id, title=title)

    def list(self, tenant_id: str) -> list[Conversation]:
        """All conversations for a tenant, newest first."""
        convs = [c for (tid, _), c in self._by_key.items() if tid == tenant_id]
        return sorted(convs, key=lambda c: c.created_at, reverse=True)

    # -- mutation ----------------------------------------------------------

    def append(self, conversation: Conversation, message: Message) -> Message:
        conversation.messages.append(message)
        return message


__all__ = [
    "ApprovalRequest",
    "Conversation",
    "ConversationStore",
    "Message",
    "Role",
]
