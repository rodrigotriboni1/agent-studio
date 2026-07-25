# The Four Seams

`agent-studio` never calls a concrete model, tool, database or authorization
engine directly. Every such call flows through one of **four seams** — Python
`Protocol`s in [`seams/`](../seams). Each seam has a working **v0 implementation**
in-repo and a named **future platform target**. Because the runtime and API
depend only on the `Protocol`, moving to the platform is an *implementation swap
via constructor injection*, not a core rewrite.

This is the decision recorded in
[ADR 0003 — TenantContext everywhere + the four seams](adr/0003-tenancy-and-seams.md).

| Seam | Protocol (symbol) | v0 implementation (in-repo) | Future platform target |
|---|---|---|---|
| Tools | `ToolProvider` — [`seams/tools.py`](../seams/tools.py) | `InMemoryToolProvider`, `MCPToolProvider` | **MCP Gateway** (Phase 2) |
| Models | `ModelProvider` — [`seams/models.py`](../seams/models.py) | `LiteLLMModelProvider`, `EchoModelProvider` | **LLM Bridge** (Phase 3) |
| Authz | `AuthzProvider` — [`seams/authz.py`](../seams/authz.py) | `ManifestAuthzProvider`, `AllowAllAuthzProvider` | **OpenFGA / SpiceDB** (Phase 1) |
| Tenancy | `TenantContext` — [`seams/tenancy.py`](../seams/tenancy.py) | single ambient default tenant | **real AuthN** (Phase 1) |

The single injection point that ties three of the four together is the runtime
constructor, [`LangGraphAgentRuntime.__init__`](../core/runtime/agent.py):

```python
LangGraphAgentRuntime(
    model_provider=...,   # ModelProvider seam
    tool_provider=...,    # ToolProvider seam
    authz=...,            # AuthzProvider seam
)
```

Each defaults to the offline v0 implementation, so `LangGraphAgentRuntime()` runs
with no network, no key and no DB under `AGENT_STUDIO_OFFLINE=1`.

---

## 1. `ToolProvider` — tool discovery + invocation

- **Protocol:** [`seams/tools.py`](../seams/tools.py) `ToolProvider` — two methods,
  both tenant-scoped:
  - `list_tools(*, tenant) -> list[ToolSpec]`
  - `invoke(name, arguments, *, tenant) -> ToolResult`
- **v0 implementation:**
  - `InMemoryToolProvider` — registers plain Python callables as tools; used by
    examples, tests, and as the fallback when no MCP server is configured. Even
    local tools are reached only through the seam.
  - `MCPToolProvider` — a thin MCP client shell (lazy session; importing the seam
    never requires the `mcp` dependency).
- **Future platform target:** the governed **MCP Gateway** (Phase 2). It
  implements this *same* `Protocol`, so it slots into the runtime unchanged.
- **How to swap:** pass a different `tool_provider=` into
  `LangGraphAgentRuntime(...)`. In the API this is the single
  [`AppState.tool_provider`](../api/services.py) that the runtime is constructed
  with. No other code changes — the runtime discovers tools via `list_tools` and
  invokes them via `invoke`, regardless of backend.
- **Governance hook:** the runtime filters the provider's tools through
  `AuthzProvider` before the model ever sees them (see
  [`LangGraphAgentRuntime._allowed_tools`](../core/runtime/agent.py)), and
  re-checks any tool the model requests before invoking it — so an omitted tool
  is **never** invoked (proven by
  [`tests/test_governance_e2e.py`](../tests/test_governance_e2e.py)).

## 2. `ModelProvider` — OpenAI-compatible model access

- **Protocol:** [`seams/models.py`](../seams/models.py) `ModelProvider` — one
  method:
  - `complete(*, model, messages, tenant, tools, temperature, **kwargs) -> ModelResponse`
- **v0 implementation:**
  - `LiteLLMModelProvider` — routes every call through LiteLLM's
    OpenAI-compatible surface; `litellm` is imported lazily. BYOK / per-tenant
    keys are resolved from `tenant.attributes["llm_keys"]` behind the seam.
  - `EchoModelProvider` — deterministic, no-network provider for tests/examples;
    echoes the last user message so CI runs with no API key.
- **Future platform target:** the self-hosted **LLM Bridge** (Phase 3) — same
  interface, zero runtime changes; swapping/adding a provider or enabling BYOK
  becomes config, not code.
- **How to swap:** pass `model_provider=` into `LangGraphAgentRuntime(...)`. Tests
  inject an in-test `ScriptedModelProvider` this way to drive the tool loop
  deterministically; the API constructs its runtime with `EchoModelProvider`
  (see [`AppState`](../api/services.py)).

## 3. `AuthzProvider` — the governance decision point

- **Protocol:** [`seams/authz.py`](../seams/authz.py) `AuthzProvider` — one
  method returning a `Decision(allowed, reason)`:
  - `check(*, resource_type: ResourceType, resource, manifest_allow, tenant) -> Decision`
  - `ResourceType` ∈ `{TOOL, MODEL, SOURCE}`.
- **v0 implementation:**
  - `ManifestAuthzProvider` — the *default*. Governance is driven purely by the
    manifest's allow-lists: if an allow-list is declared for a resource type, the
    resource must be in it; if none is declared (`manifest_allow is None`), allow
    (the "allow-all in v0" rule — see [governance.md](governance.md)).
  - `AllowAllAuthzProvider` — dev/example escape hatch; never for a deployed
    tenant.
- **Future platform target:** **OpenFGA / SpiceDB** (Phase 1). The call sites
  already exist at every model/tool/source access, so the FGA backend is an
  implementation swap — the runtime keeps calling `authz.check(...)` unchanged.
- **How to swap:** pass `authz=` into `LangGraphAgentRuntime(...)`. The E2E model
  denial test injects a custom `DenyModelAuthz` here to force a negative MODEL
  decision — exactly the shape an FGA tuple-deny will return later.
- **Where it is enforced:** the model gate at the top of
  [`LangGraphAgentRuntime.run`](../core/runtime/agent.py) (raises
  `ModelAccessDenied` on a negative MODEL decision), and the tool filter/re-check
  in `_allowed_tools` / the tools node.

## 4. `TenantContext` — carry the tenant everywhere

- **Interface:** [`seams/tenancy.py`](../seams/tenancy.py) `TenantContext`
  (frozen dataclass: `tenant_id`, `principal`, `attributes`) plus the ambient
  helpers `current_tenant()` and `use_tenant(ctx)`. The canonical isolation
  primitive is `ctx.namespaced(key)` → `"{tenant_id}:{key}"`.
- **v0 implementation:** a single ambient default tenant (`DEFAULT_TENANT_ID =
  "default"`) is fine, but the plumbing already threads `tenant_id` through data,
  vectors, credentials and every authz decision. See
  [`InMemoryRagIndex`](../core/rag/memory.py), whose store is keyed by
  `ctx.namespaced(source)` — this is what makes cross-tenant retrieval impossible
  (proven by the tenant-isolation case in the E2E test).
- **Future platform target:** the real **AuthN** layer (Phase 1) populates
  `TenantContext` (and `attributes` = roles/groups/plan tier), with zero changes
  to callers.
- **How to swap:** the tenant enters at the boundary. In the API it is resolved
  from the `X-Tenant-Id` header (`_resolve_tenant` in
  [`api/routers/runs.py`](../api/routers/runs.py) and
  [`api/routers/agents.py`](../api/routers/agents.py)); the runtime binds it
  ambiently with `use_tenant(tenant)` and *also* passes it explicitly to every
  seam call. Replacing header-based resolution with real AuthN touches only the
  boundary resolver.

---

## Proof

Governance across three of these seams (Authz over Tools + Models, and Tenancy
over vectors) is proven end-to-end, offline, in
[`tests/test_governance_e2e.py`](../tests/test_governance_e2e.py). See
[governance.md](governance.md) for how the manifest allow-lists become the
enforced surface, and how this maps onto FGA later without runtime changes.
