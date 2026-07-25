"""LlamaIndex + pgvector RagIndex (spec §5.2).

``PgVectorRagIndex`` is the production retrieval engine: it stores embedded
chunks in Postgres via ``llama_index.vector_stores.postgres.PGVectorStore`` and
retrieves them with LlamaIndex.

TENANT ISOLATION is structural, not advisory: each ``(tenant, source)`` pair maps
to its OWN pgvector table (``data_<prefix>_<tenant>_<source>``). Tenant A and
tenant B therefore write to and read from different tables, so a query in one
tenant's scope can never surface another tenant's vectors.

All heavy imports (llama-index, psycopg, sqlalchemy) are performed lazily inside
methods/constructor so that merely importing this module never requires a DB,
those packages, or a network — keeping the offline default green.
"""

from __future__ import annotations

import os
import re
from typing import Any

from core.rag import Document, RetrievedChunk
from seams.tenancy import TenantContext, current_tenant

# Default embedding dimension. pgvector columns are fixed-width, so this must
# match whatever embedding model the environment configures on LlamaIndex's
# ``Settings.embed_model`` (1536 == OpenAI text-embedding-3-small / ada-002).
_DEFAULT_EMBED_DIM = 1536
_SANITIZE_RE = re.compile(r"[^a-z0-9]+")


def _sanitize(value: str) -> str:
    """Reduce an identifier to ``[a-z0-9_]`` so it is safe as a table suffix."""
    return _SANITIZE_RE.sub("_", value.lower()).strip("_") or "default"


class PgVectorRagIndex:
    """RagIndex backed by LlamaIndex + PGVectorStore.

    Args:
        database_url: Postgres DSN. Defaults to ``$DATABASE_URL``.
        table_prefix: prefix shared by every per-tenant table.
        embed_dim: embedding dimension of the configured embed model.
    """

    def __init__(
        self,
        *,
        database_url: str | None = None,
        table_prefix: str = "agent_studio_rag",
        embed_dim: int = _DEFAULT_EMBED_DIM,
    ) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if not self.database_url:
            raise ValueError(
                "PgVectorRagIndex requires DATABASE_URL (env) or database_url= arg"
            )
        self.table_prefix = table_prefix
        self.embed_dim = embed_dim

    def _table_name(self, source: str, tenant: TenantContext) -> str:
        """Per-tenant, per-source table name — the isolation boundary.

        PGVectorStore prepends ``data_`` to whatever name we pass, yielding a
        physical table like ``data_<prefix>_<tenant>_<source>``.
        """
        return f"{self.table_prefix}_{_sanitize(tenant.tenant_id)}_{_sanitize(source)}"

    def _make_store(self, source: str, tenant: TenantContext) -> Any:
        """Build a tenant-scoped PGVectorStore (lazy heavy imports)."""
        from llama_index.vector_stores.postgres import PGVectorStore

        return PGVectorStore.from_params(
            connection_string=self.database_url,
            table_name=self._table_name(source, tenant),
            embed_dim=self.embed_dim,
        )

    def ingest(
        self,
        source: str,
        documents: list[Document],
        *,
        tenant: TenantContext | None = None,
    ) -> int:
        from llama_index.core import Document as LlamaDocument
        from llama_index.core import StorageContext, VectorStoreIndex
        from llama_index.core.node_parser import SentenceSplitter

        tenant = tenant or current_tenant()
        store = self._make_store(source, tenant)
        storage_context = StorageContext.from_defaults(vector_store=store)

        llama_docs = [
            LlamaDocument(
                text=doc.text,
                id_=doc.id,
                # Carry provenance so retrieval can cite the source document.
                metadata={**doc.metadata, "source": source, "doc_id": doc.id},
            )
            for doc in documents
        ]
        splitter = SentenceSplitter()
        nodes = splitter.get_nodes_from_documents(llama_docs)
        VectorStoreIndex(
            nodes,
            storage_context=storage_context,
        )
        return len(nodes)

    def retrieve(
        self,
        source: str,
        query: str,
        *,
        top_k: int = 4,
        rerank: bool = False,
        tenant: TenantContext | None = None,
    ) -> list[RetrievedChunk]:
        from llama_index.core import VectorStoreIndex

        tenant = tenant or current_tenant()
        store = self._make_store(source, tenant)
        index = VectorStoreIndex.from_vector_store(store)
        retriever = index.as_retriever(similarity_top_k=top_k)
        results = retriever.retrieve(query)

        chunks: list[RetrievedChunk] = []
        for node_with_score in results:
            node = node_with_score.node
            metadata = {str(k): str(v) for k, v in (node.metadata or {}).items()}
            chunks.append(
                RetrievedChunk(
                    text=node.get_content(),
                    score=float(node_with_score.score or 0.0),
                    source=metadata.get("source", source),
                    metadata=metadata,
                )
            )
        return chunks
