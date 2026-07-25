# ADR 0002 — RAG: LlamaIndex + pgvector for v0

Status: accepted (answers spec §8 Q1 & Q2)

## Decision
- **RAG framework: LlamaIndex.** Default for agentic RAG; strongest ingest/
  index/re-rank/connector story. Haystack is the "enterprise pipeline" fallback
  if a heavier deployment needs it later — but it does not change the
  `core.rag.RagIndex` interface.
- **Vector store: pgvector.** Reuses the Postgres we already run; one fewer
  dependency for v0. Qdrant/Milvus become a drop-in behind `RagIndex` at scale.

## Rationale
Simplicity first. The `RagIndex` Protocol (ingest/retrieve, tenant-scoped) is the
stable contract; the concrete engine and store sit behind it, so swapping either
is an implementation change, not an interface change.

## Consequences
Vectors are namespaced by `tenant_id` (see ADR-0003). Re-rank is opt-in per RAG
source in the manifest (`RagSourceRef.rerank`).
