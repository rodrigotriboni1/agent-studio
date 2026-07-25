"""ToolProvider seam.

Rule (spec §4): an agent NEVER calls a concrete tool. It resolves and invokes
tools through this seam. The v0 implementation is a thin MCP client; later the
exact same interface is backed by the governed **MCP Gateway** (platform Phase 2)
— zero rewrites in the runtime.

Governance hook: ``list_tools``/``invoke`` are tenant-scoped, and the runtime is
expected to filter the returned set through ``AuthzProvider`` so a manifest only
ever sees the tools it is allowed to use.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from seams.tenancy import TenantContext, current_tenant


@dataclass
class ToolSpec:
    """MCP-shaped tool description (name + JSON schema)."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    content: Any
    is_error: bool = False


@runtime_checkable
class ToolProvider(Protocol):
    """Discover and invoke tools. Implementations MUST be tenant-scoped."""

    def list_tools(self, *, tenant: TenantContext | None = None) -> list[ToolSpec]:
        ...

    def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        tenant: TenantContext | None = None,
    ) -> ToolResult:
        ...


class InMemoryToolProvider:
    """Register plain Python callables as tools. Used by examples/tests and as
    the fallback when no MCP server is configured. Keeps the runtime honest:
    even local tools are reached only through the seam."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolSpec, Callable[..., Any]]] = {}

    def register(self, spec: ToolSpec, fn: Callable[..., Any]) -> None:
        self._tools[spec.name] = (spec, fn)

    def list_tools(self, *, tenant: TenantContext | None = None) -> list[ToolSpec]:
        return [spec for spec, _ in self._tools.values()]

    def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        tenant: TenantContext | None = None,
    ) -> ToolResult:
        tenant = tenant or current_tenant()
        entry = self._tools.get(name)
        if entry is None:
            return ToolResult(content=f"unknown tool: {name}", is_error=True)
        _, fn = entry
        try:
            return ToolResult(content=fn(**arguments))
        except Exception as exc:  # surface tool errors to the agent, don't crash
            return ToolResult(content=f"{type(exc).__name__}: {exc}", is_error=True)


class MCPToolProvider:
    """v0 MCP client. Connects to one or more MCP servers declared per tenant
    and exposes their tools through the seam. The concrete MCP session is created
    lazily so importing the seam never requires the ``mcp`` dependency.

    NOTE: this is intentionally a *simple* client. The governed MCP Gateway
    (platform Phase 2) will implement this same Protocol and slot in unchanged.
    """

    def __init__(self, server_command: list[str] | None = None) -> None:
        self.server_command = server_command or []
        self._delegate = InMemoryToolProvider()  # until a live session is wired

    def list_tools(self, *, tenant: TenantContext | None = None) -> list[ToolSpec]:
        # Real MCP session enumeration lands in core/runtime wiring; the seam
        # contract and fallback are defined here so the runtime can depend on it.
        return self._delegate.list_tools(tenant=tenant)

    def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        tenant: TenantContext | None = None,
    ) -> ToolResult:
        return self._delegate.invoke(name, arguments, tenant=tenant)
