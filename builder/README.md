# Agent Studio Builder

Minimal React + shadcn/ui frontend for the Agent Studio API. This is a thin
client over the FastAPI contract (see ADR-0004, API-first): every capability is
reachable via the API/CLI first — the UI just consumes it.

## Dev setup

```bash
cd builder
pnpm install
pnpm dev          # Vite dev server at http://localhost:5173
```

## Mock mode (default in dev)

By default (`VITE_USE_MOCKS` unset or `!= "0"`), all API calls are handled by an
in-memory fetch shim (`src/lib/mockFetch.ts` + `src/lib/mocks.ts`). You can run
and click through the **entire UI without a live backend**. The fixtures include:

- two agents (a published "Support Bot" with RAG + tools, a draft "Code Reviewer"),
- a run result with a citation **and** a governance denial (`send_email`),
- a paused workflow in `WAITING_APPROVAL`.

To connect to a real backend instead:

```bash
# Option A — Vite dev proxy (recommended, avoids CORS in dev)
VITE_USE_MOCKS=0 pnpm dev
# The dev server proxies /api/* -> http://localhost:8000/* automatically.

# Option B — direct URL (requires CORSMiddleware on the backend)
VITE_USE_MOCKS=0 VITE_API_URL=http://localhost:8000 pnpm dev
```

## Screens

| Route | Screen | What it does |
|-------|--------|--------------|
| `/` | **Agents list** | Cards for every agent (name, status, model, version, tools) with Edit/Run links and a **New Agent** button. |
| `/agents/new` | **Agent editor** | Create a new draft agent. |
| `/agents/:id` | **Agent editor** | Edit name, description, system prompt, model, allowed tools (add/remove), allowed models (add/remove), RAG sources (name / top_k / rerank), and guardrails (max_tokens, temperature, max_tool_calls). Save draft, **Publish**, and roll back from the **Version History** list. |
| `/agents/:id/run` | **Run panel** | Send a message and view the `RunResult`: answer, citations (source + score), tool calls, and **governance denials** (tools/models refused by the manifest allow-list). |
| `/workflows` | **Workflow runner** | Start the demo workflow (triage → human review → specialist). When it pauses in `WAITING_APPROVAL`, use **Approve** / **Reject** — both call the `resume` endpoint. |
| `/chat` | **Chat** | Multi-turn conversation with an agent (SSE streaming) or a workflow (HITL). Left rail lists past conversations; agent/workflow selector in the header. Assistant messages show citation chips, tool-call chips, governance denial chips (red), and inline Approve/Reject cards for workflow pauses. |
| `/history` | **History** | Browse past conversations read-only; click any to read messages. "Continue in chat" link reopens in `/chat/:id`. |

The editor form mirrors `core/manifest/schema.py` (`AgentManifest`), and the run
panel mirrors `core/runtime` (`RunResult`: output, tool_calls, citations, denied).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | FastAPI base URL. |
| `VITE_USE_MOCKS` | `1` (on) | Set to `0` to disable mocks and hit a real backend. |

All requests send an `X-Tenant-Id` header (default `default`); override with
`setTenantId()` in `src/lib/api.ts`.

## API client

`src/lib/api.ts` is a typed client for the FastAPI contract:

- Agents CRUD — `GET/POST /agents`, `GET/PUT /agents/{id}`
- Versioning — `POST /agents/{id}/publish`, `GET /agents/{id}/versions`, `POST /agents/{id}/rollback`
- Run — `POST /agents/{id}/run`
- RAG ingest — `POST /sources/{name}/ingest`
- Workflows — `POST /workflows/run`, `POST /workflows/{id}/resume`
- Chat — `POST /agents/{id}/chat`, `POST /agents/{id}/chat/stream` (SSE), `GET /conversations`, `GET /conversations/{id}`, `POST /workflows/chat`, `POST /conversations/{id}/resume`

## Build & lint

```bash
pnpm build    # tsc -b + Vite bundle → dist/
pnpm lint     # ESLint (flat config, zero warnings allowed)
```
