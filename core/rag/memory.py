"""Offline, dependency-free RAG index (spec §5.2).

``InMemoryRagIndex`` is the OFFLINE default: it needs no embeddings, no vector
database and no network. It splits documents into chunks with a naive splitter,
stores them in per-``(tenant, source)`` buckets, and retrieves by scoring
keyword/token overlap between the query and each chunk.

EVERYTHING is tenant-scoped: chunks live under ``ctx.namespaced(source)`` so a
retrieve for tenant B can NEVER see tenant A's data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.rag import Document, RetrievedChunk
from seams.tenancy import TenantContext, current_tenant

# A conservative default so a short document still yields a couple of chunks
# while long documents are split into retrievable units.
_DEFAULT_CHUNK_SIZE = 512
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens — the shared vocabulary for scoring."""
    return _TOKEN_RE.findall(text.lower())


def _split(text: str, chunk_size: int) -> list[str]:
    """Naive whitespace-aware splitter: pack words up to ``chunk_size`` chars.

    Keeps whole words together and never emits empty chunks.
    """
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        # +1 for the joining space once the buffer is non-empty.
        extra = len(word) + (1 if current else 0)
        if current and length + extra > chunk_size:
            chunks.append(" ".join(current))
            current = [word]
            length = len(word)
        else:
            current.append(word)
            length += extra
    if current:
        chunks.append(" ".join(current))
    return chunks


@dataclass
class _StoredChunk:
    """A stored chunk plus its provenance and precomputed token set."""

    text: str
    source: str
    metadata: dict[str, str]
    tokens: frozenset[str]


@dataclass
class InMemoryRagIndex:
    """Embedding-free, in-process RagIndex implementation.

    Args:
        chunk_size: maximum characters per chunk for the naive splitter.
    """

    chunk_size: int = _DEFAULT_CHUNK_SIZE
    # Keyed by the tenant-namespaced source (e.g. ``"acme:docs"``).
    _store: dict[str, list[_StoredChunk]] = field(default_factory=dict)

    def _key(self, source: str, tenant: TenantContext) -> str:
        return tenant.namespaced(source)

    def ingest(
        self,
        source: str,
        documents: list[Document],
        *,
        tenant: TenantContext | None = None,
    ) -> int:
        tenant = tenant or current_tenant()
        key = self._key(source, tenant)
        bucket = self._store.setdefault(key, [])
        added = 0
        for doc in documents:
            for i, piece in enumerate(_split(doc.text, self.chunk_size)):
                metadata = dict(doc.metadata)
                # Citation provenance: which document/chunk this came from.
                metadata.setdefault("doc_id", doc.id)
                metadata["chunk_index"] = str(i)
                bucket.append(
                    _StoredChunk(
                        text=piece,
                        source=source,
                        metadata=metadata,
                        tokens=frozenset(_tokenize(piece)),
                    )
                )
                added += 1
        return added

    def retrieve(
        self,
        source: str,
        query: str,
        *,
        top_k: int = 4,
        rerank: bool = False,
        tenant: TenantContext | None = None,
    ) -> list[RetrievedChunk]:
        tenant = tenant or current_tenant()
        key = self._key(source, tenant)
        bucket = self._store.get(key, [])
        query_tokens = set(_tokenize(query))
        if not bucket or not query_tokens:
            return []

        scored: list[RetrievedChunk] = []
        for chunk in bucket:
            overlap = query_tokens & chunk.tokens
            if not overlap:
                continue
            # Jaccard-like score in [0, 1]: shared tokens over the union of the
            # query and chunk vocabularies. Deterministic and dependency-free.
            union = query_tokens | chunk.tokens
            score = len(overlap) / len(union)
            scored.append(
                RetrievedChunk(
                    text=chunk.text,
                    score=score,
                    source=chunk.source,
                    metadata=dict(chunk.metadata),
                )
            )

        # Highest score first; stable tie-break keeps ingest order for equal scores.
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]
