"""JSON-file-backed ManifestStore — persistent, tenant-scoped.

Implements the same :class:`~core.manifest.store.ManifestStore` Protocol as
:class:`~core.manifest.store.InMemoryManifestStore` but flushes the store to a
JSON file after every write so state survives across process invocations.

Storage layout on disk::

    {
        "<tenant_id>:<agent_id>:<version>": { ...AgentManifest.model_dump()... },
        ...
    }

The key format mirrors the in-memory ``(tenant_id, agent_id, version)`` triple
serialised as a colon-joined string so it is human-readable in the file.

Thread-safety is *not* guaranteed — JSON I/O is single-process, single-thread
(this is an offline / CLI helper).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.manifest.schema import AgentManifest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_store_path() -> Path:
    """Return the default store path, preferring the local project directory."""
    return Path(".agent-studio-store.json")


def _key(tenant_id: str, agent_id: str, version: int) -> str:
    return f"{tenant_id}:{agent_id}:{version}"


def _parse_key(k: str) -> tuple[str, str, int]:
    """Reverse of ``_key``.  Splits on the LAST two colons so tenant_id may
    itself contain colons (e.g. ``org:team``)."""
    parts = k.rsplit(":", 2)
    if len(parts) != 3:
        raise ValueError(f"malformed store key: {k!r}")
    tid, aid, ver = parts
    return tid, aid, int(ver)


# ---------------------------------------------------------------------------
# JSONManifestStore
# ---------------------------------------------------------------------------


class JSONManifestStore:
    """File-backed, offline implementation of :class:`~core.manifest.store.ManifestStore`.

    Args:
        path: Path to the JSON file.  Created on first write if absent.
            Defaults to :func:`_default_store_path`.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path: Path = Path(path) if path is not None else _default_store_path()
        self._data: dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # ManifestStore implementation
    # ------------------------------------------------------------------

    def save(self, manifest: AgentManifest) -> None:
        """Persist *manifest*, overwriting any existing record for the same
        ``(tenant_id, id, version)`` triple."""
        k = _key(manifest.tenant_id, manifest.id, manifest.version)
        self._data[k] = manifest.model_dump(mode="json")
        self._flush()

    def get(
        self,
        tenant_id: str,
        agent_id: str,
        version: int | None = None,
    ) -> AgentManifest:
        """Return the manifest at *version*, or the latest when *version* is ``None``.

        Raises :exc:`KeyError` when no matching record exists.
        """
        if version is not None:
            k = _key(tenant_id, agent_id, version)
            if k not in self._data:
                raise KeyError(f"No manifest for ({tenant_id!r}, {agent_id!r}, v{version})")
            return AgentManifest.model_validate(self._data[k])

        # Latest = highest version number for this (tenant, agent)
        candidates = [
            AgentManifest.model_validate(v)
            for k, v in self._data.items()
            if k.startswith(f"{tenant_id}:{agent_id}:")
            and _parse_key(k)[:2] == (tenant_id, agent_id)
        ]
        if not candidates:
            raise KeyError(f"No manifest for ({tenant_id!r}, {agent_id!r})")
        return max(candidates, key=lambda m: m.version)

    def list(self, tenant_id: str) -> list[AgentManifest]:
        """Return the latest version of every agent owned by *tenant_id*."""
        agent_ids: set[str] = set()
        for k in self._data:
            try:
                tid, aid, _ = _parse_key(k)
            except ValueError:
                continue
            if tid == tenant_id:
                agent_ids.add(aid)

        result = []
        for agent_id in sorted(agent_ids):
            result.append(self.get(tenant_id, agent_id))
        return result

    def history(self, tenant_id: str, agent_id: str) -> list[AgentManifest]:
        """Return all versions of *agent_id* for *tenant_id*, ascending."""
        versions: list[AgentManifest] = []
        for k, v in self._data.items():
            try:
                tid, aid, _ = _parse_key(k)
            except ValueError:
                continue
            if tid == tenant_id and aid == agent_id:
                versions.append(AgentManifest.model_validate(v))
        return sorted(versions, key=lambda m: m.version)
