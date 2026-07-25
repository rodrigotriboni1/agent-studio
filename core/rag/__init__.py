"""RAG behind an interface (spec §5.2).

The retrieval interface is deliberately trivial so the concrete engine
(LlamaIndex + pgvector today) is swappable. EVERYTHING is tenant-scoped: vectors
are namespaced by ``tenant_id`` so no cross-tenant leakage is possible.

CONTRACT (implemented by story 5.2). Concrete implementation lives in
``core/rag/llamaindex_pgvector.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from seams.tenancy import TenantContext


@dataclass
class Document:
    """A raw document to ingest."""

    id: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RetrievedChunk:
    """A retrieved chunk with provenance for citation."""

    text: str
    score: float
    source: str
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class RagIndex(Protocol):
    """Ingest and retrieve, always within one source and one tenant."""

    def ingest(
        self,
        source: str,
        documents: list[Document],
        *,
        tenant: TenantContext | None = None,
    ) -> int:
        """Ingest documents into ``source``; return chunk count."""
        ...

    def retrieve(
        self,
        source: str,
        query: str,
        *,
        top_k: int = 4,
        rerank: bool = False,
        tenant: TenantContext | None = None,
    ) -> list[RetrievedChunk]:
        ...


# Concrete implementations + factory are imported after the contract above so
# they can safely ``from core.rag import Document, RetrievedChunk`` without a
# circular-import failure at package init.
from core.rag.factory import make_rag_index  # noqa: E402
from core.rag.llamaindex_pgvector import PgVectorRagIndex  # noqa: E402
from core.rag.memory import InMemoryRagIndex  # noqa: E402

__all__ = [
    "Document",
    "RetrievedChunk",
    "RagIndex",
    "make_rag_index",
    "InMemoryRagIndex",
    "PgVectorRagIndex",
]
