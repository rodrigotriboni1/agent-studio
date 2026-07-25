"""RAG tests (spec §5.2) — offline, using the dependency-free InMemoryRagIndex.

These lock the behaviour the whole RAG story guarantees: cited retrieval,
relevance ranking, top_k, and — critically — tenant isolation. A pgvector
integration test is included but SKIPPED unless DATABASE_URL is set so CI stays
offline-green.
"""

from __future__ import annotations

import os

import pytest

from core.rag import (
    Document,
    InMemoryRagIndex,
    PgVectorRagIndex,
    RagIndex,
    RetrievedChunk,
    make_rag_index,
)
from seams.tenancy import TenantContext

DOCS = [
    Document(
        id="d1",
        text="The capital of France is Paris, a city on the Seine.",
        metadata={"title": "France"},
    ),
    Document(
        id="d2",
        text="Photosynthesis lets plants convert sunlight into chemical energy.",
        metadata={"title": "Biology"},
    ),
    Document(
        id="d3",
        text="The Great Barrier Reef is the world's largest coral reef system.",
        metadata={"title": "Oceans"},
    ),
]


def test_ingest_and_retrieve_most_relevant_chunk():
    index = InMemoryRagIndex()
    count = index.ingest("docs", DOCS, tenant=TenantContext(tenant_id="acme"))
    assert count >= len(DOCS)

    results = index.retrieve(
        "docs", "What is the capital of France?", top_k=1,
        tenant=TenantContext(tenant_id="acme"),
    )
    assert len(results) == 1
    top = results[0]
    assert isinstance(top, RetrievedChunk)
    assert "Paris" in top.text
    assert top.source == "docs"
    assert top.score > 0.0


def test_retrieved_chunk_has_citation_metadata():
    index = InMemoryRagIndex()
    index.ingest("docs", DOCS, tenant=TenantContext(tenant_id="acme"))

    results = index.retrieve(
        "docs", "coral reef system", top_k=1,
        tenant=TenantContext(tenant_id="acme"),
    )
    assert results
    meta = results[0].metadata
    # Provenance for citation: which document + chunk, plus original metadata.
    assert meta["doc_id"] == "d3"
    assert "chunk_index" in meta
    assert meta["title"] == "Oceans"


def test_tenant_isolation_no_cross_tenant_leakage():
    index = InMemoryRagIndex()
    tenant_a = TenantContext(tenant_id="a")
    tenant_b = TenantContext(tenant_id="b")

    index.ingest(
        "docs",
        [Document(id="secret", text="Tenant A confidential Paris dossier")],
        tenant=tenant_a,
    )

    # Tenant B queries the same source name + a matching query: must get nothing.
    leaked = index.retrieve("docs", "Paris dossier", tenant=tenant_b)
    assert leaked == []

    # Tenant A still sees its own data.
    own = index.retrieve("docs", "Paris dossier", tenant=tenant_a)
    assert own and "Paris" in own[0].text


def test_top_k_is_respected():
    index = InMemoryRagIndex()
    tenant = TenantContext(tenant_id="acme")
    # Many small docs that all share the query token "reef".
    docs = [Document(id=f"r{i}", text=f"reef fact number {i}") for i in range(10)]
    index.ingest("reefs", docs, tenant=tenant)

    for k in (1, 3, 5):
        results = index.retrieve("reefs", "reef", top_k=k, tenant=tenant)
        assert len(results) == k


def test_scores_are_ranked_descending():
    index = InMemoryRagIndex()
    tenant = TenantContext(tenant_id="acme")
    # Two docs share query tokens with differing overlap so ranking is exercised.
    ranked_docs = [
        Document(id="strong", text="Paris is the capital city of France on the Seine"),
        Document(id="weak", text="Paris hosts a famous museum"),
        Document(id="none", text="Photosynthesis converts sunlight into energy"),
    ]
    index.ingest("docs", ranked_docs, tenant=tenant)

    results = index.retrieve(
        "docs", "capital city of France Paris Seine", top_k=3, tenant=tenant
    )
    assert len(results) >= 2
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    # The strongly-overlapping chunk should rank first.
    assert results[0].metadata["doc_id"] == "strong"
    assert results[0].score > results[1].score


def test_empty_query_and_unknown_source_return_empty():
    index = InMemoryRagIndex()
    tenant = TenantContext(tenant_id="acme")
    index.ingest("docs", DOCS, tenant=tenant)

    assert index.retrieve("docs", "", tenant=tenant) == []
    assert index.retrieve("missing-source", "France", tenant=tenant) == []


def test_in_memory_satisfies_ragindex_protocol():
    assert isinstance(InMemoryRagIndex(), RagIndex)


def test_factory_offline_returns_in_memory(monkeypatch):
    monkeypatch.setenv("AGENT_STUDIO_OFFLINE", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")  # ignored when offline
    assert isinstance(make_rag_index(), InMemoryRagIndex)


def test_factory_without_database_url_returns_in_memory(monkeypatch):
    monkeypatch.delenv("AGENT_STUDIO_OFFLINE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert isinstance(make_rag_index(), InMemoryRagIndex)


def test_pgvector_module_imports_without_db():
    # Importing the module (and the class) must NOT require a DB or heavy deps.
    assert PgVectorRagIndex is not None


def test_pgvector_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError):
        PgVectorRagIndex()


def test_pgvector_table_names_are_tenant_isolated(monkeypatch):
    monkeypatch.delenv("AGENT_STUDIO_OFFLINE", raising=False)
    index = PgVectorRagIndex(database_url="postgresql://localhost/test")
    table_a = index._table_name("docs", TenantContext(tenant_id="a"))
    table_b = index._table_name("docs", TenantContext(tenant_id="b"))
    assert table_a != table_b
    assert "_a_" in table_a and "_b_" in table_b


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL") or os.environ.get("AGENT_STUDIO_OFFLINE") == "1",
    reason="pgvector integration test needs a live DATABASE_URL and non-offline mode",
)
def test_pgvector_integration_ingest_and_retrieve():  # pragma: no cover
    index = PgVectorRagIndex()
    tenant = TenantContext(tenant_id="itest")
    count = index.ingest("docs", DOCS, tenant=tenant)
    assert count > 0
    results = index.retrieve("docs", "capital of France", top_k=1, tenant=tenant)
    assert results
    assert results[0].source == "docs"
