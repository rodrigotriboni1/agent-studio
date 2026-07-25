"""AuthzProvider seam.

Rule (spec §4): EVERY "can this agent use this tool / this model / this data
source?" decision flows through this interface. v0 returns allow-by-default for a
single tenant, but the call sites already exist — so pointing at OpenFGA/SpiceDB
(platform Phase 1) is an implementation swap, not a runtime rewrite.

The governance value of the whole product lives here: the manifest declares an
*allow-list* of models/tools/sources, and this seam is where that list is
enforced at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from seams.tenancy import TenantContext, current_tenant


class ResourceType(StrEnum):
    TOOL = "tool"
    MODEL = "model"
    SOURCE = "source"  # a RAG source / knowledge collection


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


@runtime_checkable
class AuthzProvider(Protocol):
    """Decides whether ``tenant`` may use ``resource`` of ``resource_type``.

    ``manifest_allow`` is the per-agent allow-list drawn from the versioned
    manifest — the primary governance signal in v0.
    """

    def check(
        self,
        *,
        resource_type: ResourceType,
        resource: str,
        manifest_allow: set[str] | None = None,
        tenant: TenantContext | None = None,
    ) -> Decision:
        ...


class ManifestAuthzProvider:
    """Default v0 provider: governance driven purely by the agent manifest's
    allow-lists (no external FGA yet). If the manifest declares an allow-list for
    a resource type, the resource must be in it; if it declares none, allow.

    This already delivers the section-6 promise: real governance (a manifest can
    only touch declared models/tools/sources) *before* a real FGA exists.
    """

    def check(
        self,
        *,
        resource_type: ResourceType,
        resource: str,
        manifest_allow: set[str] | None = None,
        tenant: TenantContext | None = None,
    ) -> Decision:
        tenant = tenant or current_tenant()
        if manifest_allow is None:
            return Decision(allowed=True, reason="no allow-list declared")
        if resource in manifest_allow:
            return Decision(allowed=True, reason="in manifest allow-list")
        return Decision(
            allowed=False,
            reason=(
                f"{resource_type.value} '{resource}' not in manifest allow-list "
                f"for tenant '{tenant.tenant_id}'"
            ),
        )


class AllowAllAuthzProvider:
    """Escape hatch for local dev / examples. Never use in a deployed tenant."""

    def check(
        self,
        *,
        resource_type: ResourceType,
        resource: str,
        manifest_allow: set[str] | None = None,
        tenant: TenantContext | None = None,
    ) -> Decision:
        return Decision(allowed=True, reason="allow-all (dev)")
