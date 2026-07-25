"""Versioned agent manifest: schema, validation, diff/rollback, store."""

from core.manifest.schema import (
    AgentManifest,
    Guardrails,
    ManifestStatus,
    MemoryConfig,
    RagSourceRef,
)
from core.manifest.store import InMemoryManifestStore, ManifestStore
from core.manifest.versioning import diff, publish, rollback

__all__ = [
    "AgentManifest",
    "Guardrails",
    "InMemoryManifestStore",
    "ManifestStatus",
    "ManifestStore",
    "MemoryConfig",
    "RagSourceRef",
    "diff",
    "publish",
    "rollback",
]
