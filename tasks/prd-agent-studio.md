# PRD — agent-studio v0

Source spec: `spec-repo-1-agent-studio.md`. Machine-readable task list: `../prd.json`.

## Goal
A **governed, multi-tenant, MCP-native** builder for agents, RAG and workflows.
Adopt the engines (LangGraph, LlamaIndex, LiteLLM, pgvector, MCP); build the
governance: versioned agent **manifest** + four **seams**
(ToolProvider, ModelProvider, AuthzProvider, TenantContext).

## Already done (foundation, on `main`)
- Repo scaffold per spec §3; AGPLv3 + commercial note; CI; Makefile; docker-compose (pgvector).
- The four seams (`seams/`) with v0 stubs + offline impls.
- Versioned manifest schema (`core/manifest/schema.py`) with governance allow-lists.
- Fixed contracts for runtime/rag/workflows (package `__init__.py`).
- Foundation tests (`tests/test_foundation.py`) green; ruff clean.
- Ralph loop installed (`scripts/ralph/`); ADRs answering spec §8.

## Stories (built in isolated worktrees, merged via PR)

| ID | Story | Spec | Wave | Model |
|----|-------|------|------|-------|
| US-001 | Manifest versioning: diff + rollback + store | 5.4 | 1 | sonnet |
| US-002 | Agent runtime via LangGraph (governed) | 5.1 | 1 | opus |
| US-003 | RAG: LlamaIndex + pgvector, cited retrieval | 5.2 | 1 | opus |
| US-004 | Workflows: multi-step + HITL | 5.3 | 1 | opus |
| US-008 | Builder UI (React + shadcn) | 5.5 | 1 | sonnet |
| US-005 | FastAPI routers | api | 2 | sonnet |
| US-006 | CLI subcommands | cli | 2 | sonnet |
| US-007 | Examples (agent, RAG, workflow) | examples | 2 | sonnet |
| US-009 | Governance v0 end-to-end + seam docs | 5.6 | 3 | opus |
| US-010 | Quickstart + Definition of Done verification | §7 | 3 | sonnet |

Wave 1 stories are independent → parallel worktrees. Wave 2 depends on wave 1;
wave 3 ties it together. Models per user directive: sonnet + opus (4.8), never fable.

## Definition of Done (spec §7)
- `git clone && make dev` runs the 3 examples with no code edits.
- Agent+RAG answers citing sources; multi-step workflow with human approval runs end-to-end.
- Versioned manifest with diff + rollback works.
- The four seams exist and are documented (even as stubs).
- README positions it clearly; AGPLv3 + commercial note live.
