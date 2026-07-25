# Governance v0 — the manifest allow-lists are the enforced surface

The governance value of the whole product lives in one place: the **agent
manifest declares allow-lists**, and the **`AuthzProvider` seam enforces them at
runtime** on every model, tool and RAG-source access. This is *governance before
a real FGA exists* — a manifest can only ever touch what it declares.

This document explains the enforced surface, the "no allow-list ⇒ allow-all in
v0" rule, and how the exact same call sites become fine-grained authorization
(OpenFGA / SpiceDB) later **without runtime changes**. The proof that it is real
(not documentation) is [`tests/test_governance_e2e.py`](../tests/test_governance_e2e.py).

## The manifest is the governance artifact

[`AgentManifest`](../core/manifest/schema.py) carries three allow-list fields —
the ONLY governance surface in v0 — plus helpers the runtime and `AuthzProvider`
consume:

| Manifest field | Helper | Meaning |
|---|---|---|
| `allowed_models: list[str]` | `allowed_model_set()` | Models this agent may use. **Always includes the primary `model`** (`{self.model, *self.allowed_models}`). |
| `allowed_tools: list[str]` | `allowed_tool_set()` | Tools this agent may call. **`None`** when the list is empty ⇒ "no allow-list declared". |
| `rag_sources: list[RagSourceRef]` | `allowed_source_set()` | RAG sources this agent may retrieve from (the `name` is the governance key). |

Manifests are versioned and immutable once published, so the enforced policy is
itself auditable Infrastructure-as-Code.

## How the allow-lists map to `AuthzProvider.check`

The runtime resolves and gates **every** resource through the `AuthzProvider`
seam ([`seams/authz.py`](../seams/authz.py)), passing the relevant allow-list as
`manifest_allow`. The three call sites in
[`LangGraphAgentRuntime`](../core/runtime/agent.py):

1. **Model gate** — first thing `run()` does, before building the graph:

   ```python
   self.authz.check(
       resource_type=ResourceType.MODEL,
       resource=manifest.model,
       manifest_allow=manifest.allowed_model_set(),
       tenant=tenant,
   )
   ```

   A negative `Decision` records the denial on the `RunResult` and raises
   `ModelAccessDenied` — the run refuses cleanly.

2. **Tool filter** (`_allowed_tools`) — before the model is even shown a tool,
   every tool the `ToolProvider` offers is checked:

   ```python
   self.authz.check(
       resource_type=ResourceType.TOOL,
       resource=spec.name,
       manifest_allow=manifest.allowed_tool_set(),
       tenant=tenant,
   )
   ```

   Denied tools are recorded in `RunResult.denied` and simply not exposed.

3. **Tool re-check at invocation** (tools node) — if the model still requests a
   non-exposed tool, it is checked again and **never invoked**; the denial is
   recorded and a "not permitted" message is returned to the model instead.

The **RAG source** allow-list (`allowed_source_set()`) is the same pattern for
`ResourceType.SOURCE`: retrieval is scoped to declared sources, and each is
tenant-namespaced in the index (see below).

`ManifestAuthzProvider.check` is the v0 decision:

```python
if manifest_allow is None:
    return Decision(allowed=True, reason="no allow-list declared")   # allow-all
if resource in manifest_allow:
    return Decision(allowed=True, reason="in manifest allow-list")
return Decision(allowed=False, reason="... not in manifest allow-list ...")
```

## What "no allow-list ⇒ allow-all in v0" means

An **empty** `allowed_tools` makes `allowed_tool_set()` return `None`, and
`ManifestAuthzProvider` reads `manifest_allow is None` as *"the author declared no
restriction for this resource type"* → **allow**. This keeps simple agents
frictionless: an agent with no tool allow-list can use whatever the tenant's
`ToolProvider` exposes.

The moment an author declares even one entry, the manifest is **closed** for that
resource type — only listed resources pass. Deny is therefore *opt-in per
resource type* in v0. (Models are the exception: `allowed_model_set()` always
seeds the primary `model`, so an agent can never accidentally lock itself out of
its own model — to deny a model you deny it at the `AuthzProvider`, which is
exactly what an FGA backend does. The E2E model-denial test forces this by
injecting a `DenyModelAuthz`.)

Tenant isolation is orthogonal and always on: the vector store keys chunks by
`TenantContext.namespaced(source)` (see
[`InMemoryRagIndex`](../core/rag/memory.py)), so tenant B can never retrieve
tenant A's data even when both use the same source name — no allow-list required.

## How this becomes FGA later — without runtime changes

The runtime does not know or care *how* `AuthzProvider.check` decides. In v0 the
decision is "is `resource` in the manifest allow-list?". In Phase 1 the same
`check(...)` call is answered by **OpenFGA / SpiceDB**: a relationship-tuple
lookup ("does tenant/principal have `can_use` on this model/tool/source?"),
optionally *combined* with the manifest allow-list still passed as
`manifest_allow`. Because:

- the call sites already exist at every model/tool/source access,
- `Decision(allowed, reason)` is already the return contract, and
- the provider is injected via `LangGraphAgentRuntime(authz=...)`
  (see [seams.md](seams.md)),

swapping to FGA is a constructor injection, not a core rewrite. The manifest
remains the declarative policy source; FGA adds tenant/principal-level tuples on
top. This is the promise in
[ADR 0003](adr/0003-tenancy-and-seams.md): *integration later = swap
implementations, not rewrite the core.*

## Proof: [`tests/test_governance_e2e.py`](../tests/test_governance_e2e.py)

Offline (`AGENT_STUDIO_OFFLINE=1`), a scripted in-test `ModelProvider` drives the
tool loop deterministically. Each denial case asserts the **side effect never
happened**, so passing means governance genuinely blocked the action:

- **Tool denial at runtime** — manifest `allowed_tools=["safe_tool"]`; the model
  requests both `safe_tool` and `danger_tool`. `danger_tool` is in
  `RunResult.denied`, its side-effect list stays **empty** (never invoked), while
  `safe_tool` IS invoked. *(A control check confirms that if `danger_tool` were
  allowed, its side effect would fire — so the empty-list assertion has teeth.)*
- **Model denial** — a `DenyModelAuthz` forces a negative `MODEL` decision,
  mirroring the runtime's real `authz.check(MODEL, ...)` call site; the run
  raises `ModelAccessDenied` and records the denial. (Comment in the test
  explains why a plain manifest can't deny its own model:
  `allowed_model_set()` always includes the primary.)
- **Tool denial via the API** — a `TestClient` against
  [`api.main.app`](../api/main.py) creates an agent whose manifest omits
  `danger_tool`, then runs it; the `/run` response surfaces the denial in its
  `denied` list and the tool's side effect never fires. A companion test proves a
  MODEL denial surfaces as **HTTP 403** with the `denied` payload
  (see [`api/routers/runs.py`](../api/routers/runs.py)).
- **Tenant isolation** — a doc ingested for tenant `acme` yields **zero** results
  when retrieved as tenant `globex`, and is retrievable by `acme`. Demonstrates
  `TenantContext` namespaces vectors.
