# agent-studio

**A governed, multi-tenant, MCP-native builder for agents, RAG and workflows.**

Not "another Dify/Langflow." The incumbents (Dify, Langflow, n8n, RAGFlow) nail
the *canvas* and miss the *governance*. `agent-studio` inverts that: it **adopts
the engines and builds the governance layer** — the versioned agent manifest,
per-tenant credential isolation, and an authorization seam deciding *which*
models, tools and data an agent may ever touch.

> **Golden rule:** adopt the engine, build the governance. We do not rewrite
> orchestration or RAG from scratch.

## What we adopt vs. what we build

| Layer | Adopted (not rewritten) |
|---|---|
| Orchestration / workflows | **LangGraph** — stateful graphs, durability, human-in-the-loop, replay |
| RAG | **LlamaIndex** — ingest, index, re-rank, connectors |
| Model routing | **LiteLLM** — multi-provider + BYOK, OpenAI-compatible |
| Vector store | **pgvector** (v0) → Qdrant/Milvus at scale |
| Tools | **MCP** — tools via protocol, never hard-coded |

**What we build — the value nobody ships together:**

- **Versioned agent manifest** (system prompt, model, allowed tools, guardrails,
  memory, RAG sources) as IaC — with diff and rollback.
- **Governance:** *which* models/tools/data an agent may touch, per tenant/team.
- **Multi-tenancy + per-tenant credential isolation** from the foundation.
- **MCP-native tools** — the agent calls tools over MCP, not proprietary plugins.

## The four seams (why this plugs into a platform later without a rewrite)

Program against four interfaces from commit 1 (`seams/`):

| Seam | Today | Later (platform) |
|---|---|---|
| `ToolProvider` | simple MCP client | MCP Gateway (Phase 2) |
| `ModelProvider` | LiteLLM (OpenAI-compat) | self-hosted LLM Bridge (Phase 3) |
| `AuthzProvider` | manifest allow-list stub | OpenFGA/SpiceDB (Phase 1) |
| `TenantContext` | carried everywhere, single default | fed by real AuthN (Phase 1) |

Respect the seams and integration becomes *swapping implementations*, not
rewriting the core.

## Repo layout

```
core/
  manifest/    # versioned agent schema + validation + diff/rollback
  runtime/     # LangGraph execution from a manifest
  rag/         # ingest/index/retrieve (LlamaIndex) behind an interface
  workflows/   # multi-step / multi-agent / human-in-the-loop graphs
seams/         # ToolProvider · ModelProvider · AuthzProvider · TenantContext
api/           # FastAPI (agent CRUD, run, ingest, versions) + CLI
builder/       # minimal React + shadcn UI
examples/      # 1 agent + 1 RAG + 1 workflow that run out of the box
docs/          # ADRs, quickstart
```

## Quick start

```bash
git clone <repo> && cd agent-studio
make dev          # deps + Postgres/pgvector up
make examples     # runs the 3 demos (agent, RAG, workflow) with no code edits
make api          # FastAPI at http://localhost:8000
make check        # lint + typecheck + tests (the ralph/CI quality gate)
```

The examples run offline by default (`AGENT_STUDIO_OFFLINE=1` → deterministic
`EchoModelProvider`), so a fresh clone is green without any API key.

## Status

v0 build is decomposed into isolated stories under `prd.json` and driven by the
[Ralph](https://ghuntley.com/ralph/) autonomous loop (`scripts/ralph/`). See
`docs/adr/` for the decisions and `tasks/` for the PRD.

## License

**AGPL-3.0-or-later** (see `LICENSE`). Commercial licensing available — see
[`COMMERCIAL.md`](COMMERCIAL.md).
