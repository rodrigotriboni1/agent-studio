"""The versioned agent manifest — the heart of agent-studio.

A manifest is Infrastructure-as-Code for an agent: system prompt, model, allowed
tools, guardrails, memory and RAG sources. It is the single governance artifact:
the ``allow`` fields here are exactly what ``AuthzProvider`` enforces at runtime.

Manifests are **immutable once published** and carry a monotonic ``version``.
Diff/rollback live in ``core.manifest.versioning``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ManifestStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Guardrails(BaseModel):
    """Coarse runtime limits + content rules. Kept declarative so the runtime
    (and later a policy engine) enforces them without code changes."""

    max_tokens: int = 2048
    temperature: float = 0.0
    max_tool_calls: int = 8
    system_suffix: str | None = None  # appended guardrail text, if any
    blocked_keywords: list[str] = Field(default_factory=list)


class MemoryConfig(BaseModel):
    kind: str = "none"  # "none" | "buffer" | "summary"
    max_messages: int = 20


class RagSourceRef(BaseModel):
    """A named RAG source the agent is allowed to retrieve from. The name is the
    governance key (matched against the AuthzProvider SOURCE allow-list)."""

    name: str
    top_k: int = 4
    rerank: bool = False


class AgentManifest(BaseModel):
    """Versioned, governable definition of a single agent.

    The ``allowed_*`` fields are the allow-lists the ``AuthzProvider`` enforces.
    A manifest can ONLY touch what it declares — this is governance-before-FGA.
    """

    # identity
    id: str
    tenant_id: str
    name: str
    description: str = ""

    # versioning
    version: int = 1
    status: ManifestStatus = ManifestStatus.DRAFT

    # behaviour
    system_prompt: str = "You are a helpful assistant."
    model: str = "gpt-4o-mini"
    guardrails: Guardrails = Field(default_factory=Guardrails)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)

    # governance allow-lists (the enforced surface)
    allowed_models: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    rag_sources: list[RagSourceRef] = Field(default_factory=list)

    # free-form metadata (owner, labels…)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("version")
    @classmethod
    def _version_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version must be >= 1")
        return v

    @field_validator("model")
    @classmethod
    def _model_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("model must not be empty")
        return v

    # --- governance helpers (consumed by runtime + AuthzProvider) ---

    def allowed_model_set(self) -> set[str]:
        """Models this manifest may use. Always includes its primary ``model``.
        Empty allow-list ⇒ only the primary model is permitted."""
        return {self.model, *self.allowed_models}

    def allowed_tool_set(self) -> set[str] | None:
        """Tools this manifest may call. ``None`` means 'no allow-list declared'
        (AuthzProvider treats that as allow-all in v0)."""
        return set(self.allowed_tools) if self.allowed_tools else None

    def allowed_source_set(self) -> set[str]:
        return {s.name for s in self.rag_sources}

    def is_published(self) -> bool:
        return self.status is ManifestStatus.PUBLISHED
