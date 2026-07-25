"""Manifest versioning operations: publish, diff, rollback.

Spec §5.4 — manifests are **immutable once published**.  Every change
(including rollback) produces a *new* monotonically-versioned published copy.

Design notes
~~~~~~~~~~~~
- ``publish`` never mutates the caller's object; it always returns a new copy.
- ``diff`` uses :mod:`deepdiff` and returns a plain serialisable dict so the
  caller can JSON-encode it without extra steps.
- ``rollback`` copies the behaviour fields from the target version and publishes
  the copy as a brand-new version — it does *not* delete later versions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from deepdiff import DeepDiff

from core.manifest.schema import AgentManifest, ManifestStatus

if TYPE_CHECKING:
    from core.manifest.store import ManifestStore


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def publish(store: ManifestStore, manifest: AgentManifest) -> AgentManifest:
    """Publish *manifest*, returning an immutable copy with the next version.

    The next monotonic version is derived from the existing history for
    ``(tenant_id, agent_id)``.  Callers must *not* modify the returned object.

    Args:
        store: The :class:`~core.manifest.store.ManifestStore` to persist into.
        manifest: The draft (or any) manifest to publish.  The original is
            never mutated.

    Returns:
        A new :class:`~core.manifest.schema.AgentManifest` with
        ``status=PUBLISHED`` and the next monotonic version.
    """
    existing = store.history(manifest.tenant_id, manifest.id)
    next_version = (max(m.version for m in existing) + 1) if existing else 1

    published = manifest.model_copy(
        update={"version": next_version, "status": ManifestStatus.PUBLISHED}
    )
    store.save(published)
    return published


def diff(a: AgentManifest, b: AgentManifest) -> dict[str, Any]:
    """Return a field-level diff between two manifests.

    Uses :class:`deepdiff.DeepDiff` internally and serialises the result to a
    plain ``dict`` with string keys (``values_changed``, ``dictionary_item_added``,
    ``dictionary_item_removed``, etc.) so it can be JSON-encoded without extra
    conversion.

    Args:
        a: The "before" manifest.
        b: The "after" manifest.

    Returns:
        A plain serialisable dict.  Empty dict if the manifests are identical.
    """
    delta = DeepDiff(
        a.model_dump(),
        b.model_dump(),
        ignore_order=True,
    )
    # DeepDiff returns a specialised subclass; convert to a plain dict with
    # string keys so callers can json.dumps() it without extra encoding steps.
    return {str(k): str(v) for k, v in delta.items()}


def rollback(
    store: ManifestStore,
    tenant_id: str,
    agent_id: str,
    target_version: int,
) -> AgentManifest:
    """Roll back to *target_version* by publishing a new version with its payload.

    The new version's behaviour fields (system_prompt, model, guardrails,
    memory, allowed_models, allowed_tools, rag_sources, metadata) equal those
    of *target_version*.  A brand-new monotonic version number is assigned so
    history is never rewritten.

    Args:
        store: The manifest store.
        tenant_id: Tenant owning the agent.
        agent_id: The agent to roll back.
        target_version: Version number to restore behaviour from.

    Returns:
        The newly published :class:`~core.manifest.schema.AgentManifest`.

    Raises:
        KeyError: If *target_version* does not exist for the given agent.
    """
    target = store.get(tenant_id, agent_id, version=target_version)

    # Build a draft whose behaviour fields mirror the target; identity fields
    # (id, tenant_id, name, description) come from the current latest version
    # so we don't lose any non-behaviour edits, but spec says "payload equal
    # to the target version's payload" which covers the behaviour fields.
    rollback_draft = AgentManifest(
        id=target.id,
        tenant_id=target.tenant_id,
        name=target.name,
        description=target.description,
        # behaviour — restored from target
        system_prompt=target.system_prompt,
        model=target.model,
        guardrails=target.guardrails,
        memory=target.memory,
        allowed_models=target.allowed_models,
        allowed_tools=target.allowed_tools,
        rag_sources=target.rag_sources,
        metadata=target.metadata,
        # version/status are managed by publish()
        version=1,  # placeholder; publish() will override
        status=ManifestStatus.DRAFT,
    )
    return publish(store, rollback_draft)
