"""TenantContext seam.

The golden rule of section 4 of the spec: carry the tenant *everywhere* from
commit 1, even while we are single-tenant. Retrofitting multi-tenancy is where
projects die. Every piece of data, every vector, every credential lookup and
every authz decision is scoped by a ``TenantContext``.

v0:   a single, ambient default tenant is fine — but the plumbing already
      threads ``tenant_id`` through the whole system.
later: ``TenantContext`` is populated by the real AuthN layer (platform Phase 1),
      with zero changes to callers.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TENANT_ID = "default"


@dataclass(frozen=True)
class TenantContext:
    """Immutable identity + scope for the current unit of work.

    Attributes:
        tenant_id: stable identifier used to namespace data, vectors and
            credentials. NEVER default this away in storage layers.
        principal: the acting user/service identity (opaque in v0).
        attributes: free-form claims (roles, groups, plan tier) the AuthzProvider
            may consult. Kept generic so the real AuthN layer can populate it.
    """

    tenant_id: str = DEFAULT_TENANT_ID
    principal: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def namespaced(self, key: str) -> str:
        """Return ``key`` namespaced by tenant — the canonical way to isolate
        rows, vector collections, cache keys and credential lookups."""
        return f"{self.tenant_id}:{key}"


# Ambient context so deep call stacks (LangGraph nodes, RAG retrievers, tool
# calls) can read the current tenant without threading it through every signature.
# Prefer explicit passing at module boundaries; use this for leaf reads.
_current: contextvars.ContextVar[TenantContext | None] = contextvars.ContextVar(
    "agent_studio_tenant", default=None
)


def current_tenant() -> TenantContext:
    """The tenant in scope for the current async/thread context (default tenant
    when none is bound)."""
    ctx = _current.get()
    return ctx if ctx is not None else TenantContext()


@contextmanager
def use_tenant(ctx: TenantContext) -> Iterator[TenantContext]:
    """Bind ``ctx`` as the ambient tenant for the duration of the block."""
    token = _current.set(ctx)
    try:
        yield ctx
    finally:
        _current.reset(token)
