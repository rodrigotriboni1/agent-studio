# ADR 0004 — API/CLI first, minimal builder UI included

Status: accepted (answers spec §8 Q4)

## Decision
Deliver the engine value (5.1–5.4: manifest, runtime, RAG, workflows, versioning)
through the **FastAPI + CLI** surface first. Ship a **minimal** React + shadcn
builder (5.5) in this repo too, but treat it as a thin client over the API — it
must not become the only way to drive the system.

## Rationale
API-first shortens the path to a usable first release and keeps the core
headless/testable. The UI is a consumer of the same API the platform will later
render with its design system (spec §6, Phase 5), so nothing is thrown away.

## Consequences
Every capability is reachable via API/CLI before it appears in the UI. The
builder is decomposed as its own story and can be built in parallel once the API
contract is stable.
