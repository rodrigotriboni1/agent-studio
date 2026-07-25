---
type: vault-readme
load_tier: 0
schema_version: 1
tags: []
---

# agent-studio — Knowledge Vault

> Entry point (Tier 0). Load this first, then descend by tier on demand.

## Tiers

- **index** — Cross-repo indexes (repo list, tech stack, domain map).
- **domains** — Bounded contexts identified across repos.
- **repos** — Per-repo deep documentation.
- **components** — Shared components/libraries reused across ≥ 2 repos.
- **infrastructure** — Deployable infra pieces the system runs on.
- **technologies** — External SDKs/providers consumed by repos.
- **relations** — Typed edges between repos (grpc/http/kafka/db/code/secret/apm).
- **cross-cutting** — Shared concerns (auth, errors, observability, testing).
- **adrs** — Architecture decision records.
- **glossary** — Canonical project terms.
- **agent-context** — Tier-1 cards, codegen rules, loading recipes.
- **meta** — Vault hygiene: pending queues, frontmatter spec, changelog.

Managed by the `ralph-vault` skill. See `.ralphvault/config.json` for the repo registry.
