"""ManifestStore seam — tenant-scoped persistence for AgentManifest versions.

The store is deliberately a plain Protocol so any backend (SQL, object-store,
in-process dict) can implement it.  ``InMemoryManifestStore`` is the offline
implementation used everywhere AGENT_STUDIO_OFFLINE=1 is set.

Tenant isolation is the golden rule (spec §4): ``get`` / ``list`` / ``history``
keyed by tenant_id must *never* return data belonging to another tenant.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.manifest.schema import AgentManifest


@runtime_checkable
class ManifestStore(Protocol):
    """Tenant-scoped, versioned persistence for :class:`AgentManifest`.

    All operations are scoped by ``tenant_id``; callers must never omit it.
    """

    def save(self, manifest: AgentManifest) -> None:
        """Persist *manifest*.  Overwrites any existing record for the same
        ``(tenant_id, id, version)`` triple."""
        ...

    def get(
        self,
        tenant_id: str,
        agent_id: str,
        version: int | None = None,
    ) -> AgentManifest:
        """Return the manifest at *version*, or the latest version when
        *version* is ``None``.

        Raises :exc:`KeyError` when no matching record exists.
        """
        ...

    def list(self, tenant_id: str) -> list[AgentManifest]:
        """Return the latest version of every agent owned by *tenant_id*."""
        ...

    def history(self, tenant_id: str, agent_id: str) -> list[AgentManifest]:
        """Return all versions of *agent_id* for *tenant_id*, ascending."""
        ...


class InMemoryManifestStore:
    """In-process, offline implementation of :class:`ManifestStore`.

    Storage layout: ``{(tenant_id, agent_id, version): AgentManifest}``

    Thread-safety is *not* guaranteed — this is an offline / test helper.
    """

    def __init__(self) -> None:
        # Key: (tenant_id, agent_id, version) → AgentManifest
        self._data: dict[tuple[str, str, int], AgentManifest] = {}

    # ------------------------------------------------------------------
    # ManifestStore implementation
    # ------------------------------------------------------------------

    def save(self, manifest: AgentManifest) -> None:
        key = (manifest.tenant_id, manifest.id, manifest.version)
        self._data[key] = manifest

    def get(
        self,
        tenant_id: str,
        agent_id: str,
        version: int | None = None,
    ) -> AgentManifest:
        if version is not None:
            key = (tenant_id, agent_id, version)
            if key not in self._data:
                raise KeyError(f"No manifest for ({tenant_id!r}, {agent_id!r}, v{version})")
            return self._data[key]

        # Latest = highest version number for this (tenant, agent)
        candidates = [
            m
            for (tid, aid, _), m in self._data.items()
            if tid == tenant_id and aid == agent_id
        ]
        if not candidates:
            raise KeyError(f"No manifest for ({tenant_id!r}, {agent_id!r})")
        return max(candidates, key=lambda m: m.version)

    def list(self, tenant_id: str) -> list[AgentManifest]:
        """Latest version of every agent owned by *tenant_id*."""
        # Collect unique agent_ids for this tenant
        agent_ids: set[str] = {
            aid for (tid, aid, _) in self._data if tid == tenant_id
        }
        result = []
        for agent_id in sorted(agent_ids):
            result.append(self.get(tenant_id, agent_id))
        return result

    def history(self, tenant_id: str, agent_id: str) -> list[AgentManifest]:
        """All versions of *agent_id* for *tenant_id*, ascending by version."""
        versions = [
            m
            for (tid, aid, _), m in self._data.items()
            if tid == tenant_id and aid == agent_id
        ]
        return sorted(versions, key=lambda m: m.version)
