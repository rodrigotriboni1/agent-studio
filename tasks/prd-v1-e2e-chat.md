# PRD — agent-studio v1: wire end-to-end + chat

Machine-readable: `../prd.json` (branchName `ralph/agent-studio-v1`). v0 archived: `../prd.v0.json`.

## Goal
Make the whole system **communicate end-to-end** and add a **chat** surface that
consumes agents **and** workflows.

- Today: governed core (manifest/runtime/rag/workflows), FastAPI, mock-mode builder.
- Gaps closed by v1: **CORS**, **multi-turn chat + streaming**, **workflow-driven chat with inline human approval**, **builder real-API mode**, real engines profile, full-stack run, CI.

## Fixed chat contract (frontend + backend build in parallel)
See `prd.json.chatContract`. Endpoints:
- `POST /agents/{id}/chat` and `/chat/stream` (SSE) — multi-turn agent chat.
- `GET /conversations`, `GET /conversations/{id}`.
- `POST /workflows/chat` — run a workflow from chat; pauses return `message.approval`.
- `POST /conversations/{id}/resume` — approve/reject to continue a paused workflow.

## Stories

| ID | Story | Wave | Model | Depends |
|----|-------|------|-------|---------|
| V1-001 | E2E audit + gap report | 0 | sonnet | — |
| V1-002 | CORS + app config | 1 | sonnet | — |
| V1-003 | Conversations + agent chat (+ SSE) | 1 | opus | — |
| V1-004 | Workflow-driven chat (HITL inline) | 1 | opus | V1-003 |
| V1-005 | Builder real-API mode | 2 | sonnet | V1-002 |
| V1-006 | Chat UI (agents + workflows) | 2 | opus | V1-003, V1-004 |
| V1-007 | Runs & conversations history UI | 2 | sonnet | V1-003 |
| V1-008 | Real engines profile (LiteLLM + pgvector) | 3 | opus | — |
| V1-009 | Full-stack compose + Makefile + quickstart | 3 | sonnet | V1-002, V1-005 |
| V1-010 | CI builder + e2e smoke + mypy pin | 3 | sonnet | — |

Models per directive: sonnet + opus (4.8), never fable. Each story built in an
isolated git worktree by a specialized subagent, verified (ruff + offline pytest /
pnpm build+lint), merged via PR.

## Definition of Done (v1)
- Builder (real mode) drives the live API with no CORS errors.
- Chat: multi-turn with an agent (streamed, citations/tool-calls/denials) AND a
  workflow chat that pauses for approval and resumes — verified in the browser.
- One command brings up db + API + UI (`make stack` / compose).
- Offline default still works (`AGENT_STUDIO_OFFLINE=1`); the four seams intact.
