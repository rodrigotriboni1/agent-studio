"""Agent runtime: execute an AgentManifest as a LangGraph.

CONTRACT (implemented by story 5.1). The runtime:
  * resolves model calls ONLY through ``ModelProvider``,
  * resolves tools ONLY through ``ToolProvider``,
  * filters every model/tool/source through ``AuthzProvider`` against the
    manifest allow-lists,
  * threads ``TenantContext`` through every node.

Concrete implementation lives in ``core/runtime/agent.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from core.manifest.schema import AgentManifest
from seams.authz import AuthzProvider
from seams.models import ModelProvider
from seams.tenancy import TenantContext
from seams.tools import ToolProvider


@dataclass
class RunResult:
    """Outcome of a single agent run."""

    output: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)  # governance denials


@runtime_checkable
class AgentRuntime(Protocol):
    def run(
        self,
        manifest: AgentManifest,
        message: str,
        *,
        tenant: TenantContext | None = None,
    ) -> RunResult:
        ...


__all__ = [
    "RunResult",
    "AgentRuntime",
    "AgentManifest",
    "ModelProvider",
    "ToolProvider",
    "AuthzProvider",
    "TenantContext",
]
