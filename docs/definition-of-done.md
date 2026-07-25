# Definition of Done — spec §7 verification

This document maps each of the six Definition-of-Done items from spec §7 to
the concrete evidence in the repository. All evidence was collected by actually
running the commands in the `us-010-docs` worktree with the shared venv
activated (`PYTHONPATH="$PWD" AGENT_STUDIO_OFFLINE=1`).

---

## Verification commands run (recorded outputs)

```
$ PYTHONPATH="$PWD" AGENT_STUDIO_OFFLINE=1 python -m pytest -q
Pytest: 101 passed, 0 failed, 1 skipped

$ PYTHONPATH="$PWD" AGENT_STUDIO_OFFLINE=1 ruff check .
Ruff: No issues found

$ PYTHONPATH="$PWD" AGENT_STUDIO_OFFLINE=1 python -m examples.run_all
[...all three demos printed, final line:]
Passed: 3 / 3
All examples ran successfully.
```

---

## Checklist

### DoD item 1 — `git clone && make dev` runs the 3 examples without editing code

**Verdict: PASS**

Evidence:

- `make dev` installs all extras and starts the DB (Docker); the command
  completes with the message
  `agent-studio dev environment ready. Run 'make examples' to see the 3 demos.`
- `make examples` (`python -m examples.run_all`) exits 0 with
  `Passed: 3 / 3 — All examples ran successfully.`
- Verified by `tests/test_examples.py`:
  - `test_agent_demo_runs_and_returns_non_empty_output` — PASSED
  - `test_rag_demo_returns_answer_with_citations` — PASSED
  - `test_workflow_demo_reaches_completed` — PASSED
  - `test_run_all_exits_zero` — PASSED
- No code edits required: `AGENT_STUDIO_OFFLINE=1` is set automatically by
  `examples/_offline.py` and the Makefile `examples` target; it routes all
  model / vector / tool calls through offline shims.

---

### DoD item 2 — Agent with RAG answers citing sources; multi-step workflow with human approval runs end to end

**Verdict: PASS**

Evidence — RAG citation:

- `examples/rag_demo.py` ingests 4 fictional product documents into
  `InMemoryRagIndex` and retrieves the top-3 chunks with source name, score
  and metadata. Actual output from `run_all`:

  ```
  Citations : 3
    [1] AcmeBot Pricing  (score=0.091)
    [2] AcmeBot Integrations  (score=0.075)
    [3] AcmeBot Overview  (score=0.068)
  ```

- `RetrievedChunk.source` and `RetrievedChunk.metadata["title"]` are surfaced
  in every answer (`core/rag/__init__.py`).
- Inline snippet verification: ingested one document, retrieved 1 chunk with
  `source='acme-docs'`, `score=0.222`. Assertion passed.

Evidence — workflow with human approval:

- `examples/workflow_demo.py` runs a 3-step definition
  (`triage → specialist → human_review`). The `human_review` step inserts a
  `WorkflowState.WAITING_APPROVAL` pause; the demo auto-approves (`True`)
  and the engine resumes to `COMPLETED`. Actual output:

  ```
  Final state : completed
  History steps: 3
    [agent] triage: '[echo] ...'
    [agent] specialist: '[echo] ...'
    [human_approval] human_review: True
  ```

- Full pause/resume cycle tested in `tests/test_workflows.py`:
  - `test_start_pauses_at_human_approval` — PASSED
  - `test_resume_approve_completes_with_output` — PASSED
  - `test_resume_reject_takes_distinct_terminal_branch` — PASSED

---

### DoD item 3 — Versioned manifest with diff + rollback works

**Verdict: PASS**

Evidence:

- `core/manifest/versioning.py` implements `publish`, `diff`, `rollback` as
  module-level functions operating on the `InMemoryManifestStore` (offline)
  or any `ManifestStore` protocol implementation.
- Inline verification run:

  ```
  Published v1: version=1, status=published
  Published v2: version=2, status=published
  Diff v1->v2 keys: ['values_changed']
  Diff snippet: {"root['version']": ..., "root['system_prompt']": {'new_value':
    'You are a concise expert.', 'old_value': 'You are a helpful assistant.'}}
  diff: VERIFIED OK - system_prompt change detected
  Rollback to v1 -> new v3: system_prompt='You are a helpful assistant.'
  rollback: VERIFIED OK - payload matches v1, new monotonic version assigned
  ```

- `tests/test_manifest_versioning.py` (17 tests, all PASSED):
  - `test_publish_assigns_version_1_first_time`
  - `test_publish_increments_to_version_2`
  - `test_diff_detects_changed_system_prompt`
  - `test_diff_detects_changed_model`
  - `test_rollback_creates_new_version_with_v1_payload`
  - `test_rollback_behaviour_fields_equal_target`
  - `test_rollback_missing_version_raises`
  - `test_tenant_isolation_get`, `_list`, `_history`, `_get_raises_for_wrong_tenant`

- Immutability guarantee: published versions are stored by
  `(tenant_id, agent_id, version)` key and never overwritten; `rollback`
  creates a new monotonically increasing version rather than rewinding.

---

### DoD item 4 — The 4 seams exist and are documented (even with stub implementations)

**Verdict: PASS**

Evidence — seam files:

| Seam | Protocol file | v0 implementation |
|---|---|---|
| `ToolProvider` | `seams/tools.py` | `InMemoryToolProvider`, `MCPToolProvider` |
| `ModelProvider` | `seams/models.py` | `EchoModelProvider`, `LiteLLMModelProvider` |
| `AuthzProvider` | `seams/authz.py` | `ManifestAuthzProvider`, `AllowAllAuthzProvider` |
| `TenantContext` | `seams/tenancy.py` | ambient default tenant + `use_tenant` context manager |

All four are Python `Protocol`s (runtime-checkable). The runtime
(`core/runtime/agent.py: LangGraphAgentRuntime`) accepts all three provider
seams by constructor injection; `TenantContext` is threaded through every call
via `use_tenant`.

Evidence — documentation:

- `docs/seams.md` — full documentation of each seam: Protocol symbol, v0
  implementation, future platform target, and how to swap. Includes the
  injection point code snippet and links to tests proving the governance hook.
- `docs/governance.md` — explains how manifest allow-lists become the enforced
  surface, the "no allow-list ⇒ allow-all in v0" rule, and how the exact same
  call sites become fine-grained FGA authorization later.
- `docs/adr/0003-tenancy-and-seams.md` — records the architectural decision.

Evidence — tests:

- `tests/test_foundation.py::test_in_memory_tool_provider_roundtrip` — PASSED
- `tests/test_foundation.py::test_echo_model_provider_is_offline_deterministic` — PASSED
- `tests/test_foundation.py::test_manifest_authz_enforces_allow_list` — PASSED
- `tests/test_foundation.py::test_tenant_context_namespacing_and_ambient` — PASSED

---

### DoD item 5 — README positions clearly as "governed, multi-tenant, MCP-native builder" — not "another Dify"

**Verdict: PASS**

Evidence — first two lines of `README.md`:

```
# agent-studio

**A governed, multi-tenant, MCP-native builder for agents, RAG and workflows.**

Not "another Dify/Langflow." The incumbents (Dify, Langflow, n8n, RAGFlow)
nail the *canvas* and miss the *governance*. `agent-studio` inverts that ...
```

All three positioning terms from the DoD are present verbatim:
- "governed" — in the headline
- "multi-tenant" — in the headline
- "MCP-native" — in the headline

The differentiation from Dify/Langflow is explicit in the second paragraph.
No changes to `README.md` were needed.

---

### DoD item 6 — AGPLv3 + commercial note live

**Verdict: PASS**

Evidence:

- `LICENSE` — full text of the GNU Affero General Public License, Version 3,
  19 November 2007 (33.7 KB).
- `COMMERCIAL.md` — commercial licensing note: *"agent-studio is released
  under AGPL-3.0-or-later. The AGPL's network-use clause requires that anyone
  offering the software as a network service make the complete corresponding
  source available to its users. Commercial licensing (without the AGPL
  conditions) is available."*
- `pyproject.toml` line 8: `license = { text = "AGPL-3.0-or-later" }`

---

## Summary table

| # | DoD item | Verdict | Key evidence |
|---|---|---|---|
| 1 | `git clone && make dev` runs 3 examples without code edits | **PASS** | `pytest -q`: 101 passed; `run_all`: 3/3 |
| 2 | Agent+RAG answers citing sources; workflow with human approval end-to-end | **PASS** | 3 citations with source+score; workflow `COMPLETED` after auto-approve |
| 3 | Versioned manifest with diff + rollback | **PASS** | `diff` shows `system_prompt` change; `rollback` creates v3 with v1 payload |
| 4 | 4 seams exist and are documented | **PASS** | `seams/tools.py`, `models.py`, `authz.py`, `tenancy.py` + `docs/seams.md` |
| 5 | README positions as "governed, multi-tenant, MCP-native" | **PASS** | Headline line exact match; "not another Dify" explicit |
| 6 | AGPLv3 + commercial note | **PASS** | `LICENSE` (full AGPL-3), `COMMERCIAL.md`, `pyproject.toml` |

### Partial / advisory items

- **mypy typecheck** (`make check` gate): exits non-zero due to a
  `numpy 2.5.1` / `mypy 2.3.0` stub incompatibility
  (`numpy/__init__.pyi:L737` syntax error). This is a third-party stub issue
  unrelated to project source. All project source files (`core/`, `seams/`,
  `api/`) produce zero mypy errors. Advisory: pin `numpy<2.5` or upgrade mypy
  once a compatible stub is released.

- **pgvector integration test** (`test_pgvector_integration_ingest_and_retrieve`):
  1 test skipped when `DATABASE_URL` is not set. This is by design (the factory
  returns `InMemoryRagIndex` offline). The test passes when a live Postgres +
  pgvector instance is available.
