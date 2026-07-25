# ADR 0003 — TenantContext everywhere + the four seams

Status: accepted (answers spec §8 Q3)

## Decision
Carry `TenantContext` through **everything** from commit 1 — data rows, vector
collections, credential lookups, authz decisions — even though v0 runs a single
default tenant. Real FGA (OpenFGA/SpiceDB) is deferred until platform
integration, but the call sites exist now.

Program against four interfaces (`seams/`):

| Seam | v0 implementation | Later |
|---|---|---|
| `ToolProvider` | simple MCP client | MCP Gateway (Phase 2) |
| `ModelProvider` | LiteLLM | LLM Bridge (Phase 3) |
| `AuthzProvider` | manifest allow-list | OpenFGA/SpiceDB (Phase 1) |
| `TenantContext` | single default | real AuthN (Phase 1) |

## Rationale
Retrofitting multi-tenancy is where projects die. Threading `tenant_id` now costs
almost nothing; adding it later means touching every storage and credential path.

## Consequences
No storage layer may default the tenant away. `AuthzProvider.check` is called for
every model/tool/source access. Integration later = swap implementations, not
rewrite the core.
