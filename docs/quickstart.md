# Quickstart

Get agent-studio running locally in about five minutes. The examples run
**fully offline** by default — no API key, no database, no network.

---

## 1. Clone and bootstrap

```bash
git clone <repo> && cd agent-studio
make dev
```

`make dev` creates a virtual environment, installs all extras
(`runtime`, `rag`, `mcp`, `dev`) and starts Postgres + pgvector via Docker
Compose. When it finishes you should see:

```
agent-studio dev environment ready. Run 'make examples' to see the 3 demos.
```

If you do not have Docker available you can still run every offline flow.
Skip `make dev` and do only:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[runtime,rag,mcp,dev]"
```

---

## 2. Run the three reference demos

```bash
make examples
# or: PYTHONPATH="$PWD" AGENT_STUDIO_OFFLINE=1 python -m examples.run_all
```

Expected output (trimmed):

```
============================================================
  1 / 3  AGENT DEMO — word_count tool, offline scripted model
============================================================

Agent answer:
  The phrase "The quick brown fox jumps over the lazy dog" contains 9 words
  and 43 characters (as counted by the word_count tool).
Tool calls  : 1
  [word_count] args={'text': 'The quick brown fox jumps over the lazy dog'}
               result='9 words, 43 characters'

Agent demo PASSED.

============================================================
  2 / 3  RAG DEMO — in-memory retrieval, fictional product docs
============================================================

Question: What is the pricing for AcmeBot?

Answer (excerpt):
  Based on the AcmeBot documentation:
  [1] AcmeBot pricing is usage-based...

Citations : 3
  [1] AcmeBot Pricing  (score=0.091)
  [2] AcmeBot Integrations  (score=0.075)
  [3] AcmeBot Overview  (score=0.068)

RAG demo PASSED.

============================================================
  3 / 3  WORKFLOW DEMO — triage → specialist → human_review
============================================================

Final state : completed
History steps: 3
  [agent] triage: '[echo] You are a support triage agent...'
  [agent] specialist: '[echo] You are a specialist...'
  [human_approval] human_review: True

Workflow demo PASSED.

============================================================
  SUMMARY
============================================================

Passed: 3 / 3
All examples ran successfully.
```

### What each demo exercises

| Demo | File | What runs |
|---|---|---|
| Agent | `examples/agent_demo.py` | Manifest-defined agent invokes `word_count` tool; offline `EchoModelProvider` |
| RAG | `examples/rag_demo.py` | Ingest 4 fictional product docs; retrieve citing 3 chunks with source + score |
| Workflow | `examples/workflow_demo.py` | triage → specialist → human_review (auto-approved); ends `COMPLETED` |

### Offline default

All three demos set `AGENT_STUDIO_OFFLINE=1` implicitly through
`examples/_offline.py`. This makes:

- **Model calls** use `EchoModelProvider` (echoes the last user message — no
  API key required).
- **RAG** uses `InMemoryRagIndex` (keyword overlap scoring — no pgvector
  required).
- **Tools** use `InMemoryToolProvider` (plain Python callables — no MCP server
  required).

To use a real model or pgvector, unset `AGENT_STUDIO_OFFLINE` and set the
appropriate environment variables (see `.env.example`).

---

## 3. Start the API server

```bash
make api
# or: .venv/bin/uvicorn api.main:app --reload --port 8000
```

The server starts at `http://localhost:8000`. In a separate terminal:

```bash
# Health check
curl -s http://localhost:8000/health | python3 -m json.tool
# {"status": "ok"}

# Version
curl -s http://localhost:8000/version | python3 -m json.tool
# {"version": "0.1.0"}

# Create an agent
curl -s -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-first-agent",
    "model": "echo",
    "system_prompt": "You are a helpful assistant."
  }' | python3 -m json.tool
# Returns the created AgentManifest with id, version=1, status="draft"

# Publish the agent (captures the id from the create response)
AGENT_ID="<id from above>"
curl -s -X POST "http://localhost:8000/agents/${AGENT_ID}/publish" | python3 -m json.tool
# Returns version=2, status="published"

# Run the agent
curl -s -X POST "http://localhost:8000/agents/${AGENT_ID}/run" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, world!"}' | python3 -m json.tool
# {"output": "[echo] Hello, world!", "tool_calls": [], "denied": []}
```

The API defaults to `AGENT_STUDIO_OFFLINE=1` when `DATABASE_URL` is not set,
so it works without Postgres for basic CRUD and run flows.

---

## 4. Full quality gate

```bash
make check
# expands to: ruff check . && mypy core seams api && pytest -q
```

Expected output:

```
ruff check .
# (no output — clean)

mypy core seams api
# Success: no issues found in <N> source files

pytest -q
# 101 passed, 1 skipped in <N>s
```

The one skipped test (`test_pgvector_integration_ingest_and_retrieve`) requires
a live Postgres + pgvector instance (`DATABASE_URL`). All other tests are
offline.

> **Mypy note:** if a `numpy` stub compatibility error appears in the mypy
> output, it is a numpy/mypy version mismatch in the dependency tree — not a
> project-source error. Project source (`core/`, `seams/`, `api/`) is clean.

---

## 5. What is built — the governance layer

agent-studio **adopts** LangGraph, LlamaIndex, LiteLLM, pgvector and MCP; it
**builds** the governance that the engines do not ship:

- **Versioned agent manifest** — `core/manifest/` — IaC for your agent's
  system prompt, model, tools, guardrails and RAG sources. Every change
  produces an immutable numbered version. `diff` and `rollback` work on any
  two versions.
- **Four seams** — `seams/` — `ToolProvider`, `ModelProvider`, `AuthzProvider`,
  `TenantContext`. The runtime depends only on these interfaces; swapping the
  backend (MCP Gateway, LLM Bridge, OpenFGA) is a constructor injection.
- **Multi-tenancy** — every data access is keyed by `TenantContext`; tenant A
  can never read tenant B's vectors, manifests or runs.

See [`docs/seams.md`](seams.md) and [`docs/governance.md`](governance.md) for
architecture details.

---

## Paths to production

| Path | What to change |
|---|---|
| Real LLM (OpenAI / Anthropic / …) | Unset `AGENT_STUDIO_OFFLINE`; set API key in `.env` |
| pgvector (real embeddings) | Set `DATABASE_URL`; run `docker compose up -d db` |
| MCP tools | Implement `MCPToolProvider` with your MCP server URL |
| Fine-grained authz | Swap `ManifestAuthzProvider` → OpenFGA/SpiceDB implementation |
| Multi-tenant AuthN | Replace header-based tenant resolver → real identity provider |
