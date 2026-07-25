# ADR 0001 — Adopt the engines, build the governance

Status: accepted

## Context
Incumbent builders (Dify, Langflow, n8n, RAGFlow) own the canvas but lack
governance, real multi-tenancy and MCP-native tooling. Rewriting orchestration or
RAG would be wasted effort and strictly worse than the state of the art.

## Decision
Adopt best-of-breed engines and build only the governance layer on top:

- Orchestration/workflows → **LangGraph**
- RAG → **LlamaIndex**
- Model routing → **LiteLLM** (OpenAI-compatible, BYOK)
- Vector store → **pgvector** (v0)
- Tools → **MCP**

The differentiated value we build: versioned agent **manifest** (IaC with diff +
rollback), **governance** allow-lists, **multi-tenancy + per-tenant credential
isolation**, **MCP-native** tools.

## Consequences
The four seams (ADR-0003) keep the engines swappable. We never fork an engine; we
wrap it behind an interface.
