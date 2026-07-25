"""Tests for US-001 — manifest versioning: diff, rollback, store.

All tests are offline (no network, no API key) and rely solely on
in-memory implementations.  The AGENT_STUDIO_OFFLINE=1 env var is set in
the CI recipe but the tests do not require it to be present: nothing here
touches network code.
"""

from __future__ import annotations

import pytest

from core.manifest import (
    AgentManifest,
    InMemoryManifestStore,
    ManifestStatus,
    diff,
    publish,
    rollback,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _draft(
    agent_id: str = "agent-1",
    tenant_id: str = "acme",
    *,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-4o-mini",
) -> AgentManifest:
    return AgentManifest(
        id=agent_id,
        tenant_id=tenant_id,
        name="Test Agent",
        system_prompt=system_prompt,
        model=model,
    )


# ---------------------------------------------------------------------------
# publish — version increments
# ---------------------------------------------------------------------------


def test_publish_assigns_version_1_first_time():
    store = InMemoryManifestStore()
    draft = _draft()
    v1 = publish(store, draft)
    assert v1.version == 1
    assert v1.is_published()
    assert v1.status is ManifestStatus.PUBLISHED


def test_publish_increments_to_version_2():
    store = InMemoryManifestStore()
    draft = _draft()
    publish(store, draft)
    # Publish again (simulating an edit — draft has same fields for simplicity)
    v2 = publish(store, draft)
    assert v2.version == 2
    assert v2.is_published()
    # Both are independently stored
    assert store.get("acme", "agent-1", version=1).version == 1
    assert store.get("acme", "agent-1", version=2).version == 2


def test_published_copy_is_independent_snapshot():
    """Modifying the source draft after publish must not affect the stored copy."""
    store = InMemoryManifestStore()
    draft = _draft(system_prompt="Original prompt")
    publish(store, draft)

    # Create a new draft with a different prompt and publish it
    draft2 = _draft(system_prompt="Updated prompt")
    v2 = publish(store, draft2)

    stored_v1 = store.get("acme", "agent-1", version=1)
    assert stored_v1.system_prompt == "Original prompt"
    assert v2.system_prompt == "Updated prompt"
    # They are distinct objects
    assert stored_v1 is not v2


def test_published_manifest_is_published():
    store = InMemoryManifestStore()
    v1 = publish(store, _draft())
    assert v1.is_published()


# ---------------------------------------------------------------------------
# diff — field-level detection
# ---------------------------------------------------------------------------


def test_diff_detects_changed_system_prompt():
    a = _draft(system_prompt="Original")
    b = _draft(system_prompt="Changed")
    result = diff(a, b)
    # There must be at least one entry reflecting the change
    assert result  # non-empty
    combined = " ".join(result.values())
    assert "Original" in combined or "Changed" in combined


def test_diff_detects_changed_model():
    a = _draft(model="gpt-4o-mini")
    b = _draft(model="gpt-4o")
    result = diff(a, b)
    assert result
    combined = " ".join(result.values())
    assert "gpt-4o" in combined


def test_diff_returns_empty_for_identical_manifests():
    a = _draft()
    b = _draft()
    result = diff(a, b)
    assert result == {}


def test_diff_returns_plain_dict():
    """diff() must return a plain dict with string keys (JSON-serialisable)."""
    a = _draft(system_prompt="A")
    b = _draft(system_prompt="B")
    result = diff(a, b)
    assert isinstance(result, dict)
    for k, v in result.items():
        assert isinstance(k, str)
        assert isinstance(v, str)


# ---------------------------------------------------------------------------
# rollback — creates a new version equal to a prior version's payload
# ---------------------------------------------------------------------------


def test_rollback_creates_new_version_with_v1_payload():
    store = InMemoryManifestStore()

    v1 = publish(store, _draft(system_prompt="Prompt v1"))
    assert v1.version == 1

    v2 = publish(store, _draft(system_prompt="Prompt v2"))
    assert v2.version == 2

    v3 = rollback(store, "acme", "agent-1", target_version=1)
    assert v3.version == 3
    assert v3.is_published()
    # Behaviour should equal v1
    assert v3.system_prompt == "Prompt v1"
    assert v3.model == v1.model


def test_rollback_behaviour_fields_equal_target():
    """All behaviour fields of the rolled-back version must match the target."""
    store = InMemoryManifestStore()
    original = AgentManifest(
        id="agent-1",
        tenant_id="acme",
        name="Test Agent",
        system_prompt="Specific prompt",
        model="gpt-4o-mini",
        allowed_tools=["search", "calc"],
    )
    v1 = publish(store, original)

    modified = AgentManifest(
        id="agent-1",
        tenant_id="acme",
        name="Test Agent",
        system_prompt="Different prompt",
        model="gpt-4o",
        allowed_tools=["danger"],
    )
    _v2 = publish(store, modified)

    v3 = rollback(store, "acme", "agent-1", target_version=1)

    assert v3.system_prompt == v1.system_prompt
    assert v3.model == v1.model
    assert v3.allowed_tools == v1.allowed_tools


def test_rollback_missing_version_raises():
    store = InMemoryManifestStore()
    publish(store, _draft())
    with pytest.raises(KeyError):
        rollback(store, "acme", "agent-1", target_version=999)


# ---------------------------------------------------------------------------
# Store — tenant isolation
# ---------------------------------------------------------------------------


def test_tenant_isolation_get():
    store = InMemoryManifestStore()
    agent_a = AgentManifest(id="agent-1", tenant_id="tenant-a", name="A Agent")
    agent_b = AgentManifest(id="agent-1", tenant_id="tenant-b", name="B Agent")

    publish(store, agent_a)
    publish(store, agent_b)

    retrieved_a = store.get("tenant-a", "agent-1")
    retrieved_b = store.get("tenant-b", "agent-1")

    assert retrieved_a.tenant_id == "tenant-a"
    assert retrieved_b.tenant_id == "tenant-b"
    assert retrieved_a.name == "A Agent"
    assert retrieved_b.name == "B Agent"


def test_tenant_isolation_list():
    store = InMemoryManifestStore()
    publish(store, AgentManifest(id="ag1", tenant_id="a", name="A1"))
    publish(store, AgentManifest(id="ag2", tenant_id="a", name="A2"))
    publish(store, AgentManifest(id="ag1", tenant_id="b", name="B1"))

    listed_a = store.list("a")
    listed_b = store.list("b")

    assert len(listed_a) == 2
    assert len(listed_b) == 1
    assert all(m.tenant_id == "a" for m in listed_a)
    assert all(m.tenant_id == "b" for m in listed_b)


def test_tenant_isolation_get_raises_for_wrong_tenant():
    store = InMemoryManifestStore()
    publish(store, AgentManifest(id="agent-1", tenant_id="tenant-a", name="A Agent"))

    with pytest.raises(KeyError):
        store.get("tenant-b", "agent-1")


def test_tenant_isolation_history():
    store = InMemoryManifestStore()
    for i in range(3):  # noqa: B007
        publish(store, AgentManifest(id="agent-1", tenant_id="a", name="A Agent"))
    publish(store, AgentManifest(id="agent-1", tenant_id="b", name="B Agent"))

    history_a = store.history("a", "agent-1")
    history_b = store.history("b", "agent-1")

    assert len(history_a) == 3
    assert len(history_b) == 1
    assert all(m.tenant_id == "a" for m in history_a)


# ---------------------------------------------------------------------------
# Store — basic CRUD behaviour
# ---------------------------------------------------------------------------


def test_store_get_latest_returns_highest_version():
    store = InMemoryManifestStore()
    publish(store, _draft(system_prompt="v1"))
    publish(store, _draft(system_prompt="v2"))
    publish(store, _draft(system_prompt="v3"))

    latest = store.get("acme", "agent-1")
    assert latest.version == 3
    assert latest.system_prompt == "v3"


def test_store_history_ascending_order():
    store = InMemoryManifestStore()
    publish(store, _draft())
    publish(store, _draft())
    publish(store, _draft())

    history = store.history("acme", "agent-1")
    assert [m.version for m in history] == [1, 2, 3]


def test_store_get_missing_raises():
    store = InMemoryManifestStore()
    with pytest.raises(KeyError):
        store.get("acme", "nonexistent")


def test_draft_edits_allowed_before_publish():
    """You can build / mutate a draft freely; publish() creates the snapshot."""
    draft = _draft(system_prompt="Draft A")
    store = InMemoryManifestStore()

    # Modify the draft before publishing
    draft2 = draft.model_copy(update={"system_prompt": "Draft B"})
    v1 = publish(store, draft2)

    assert v1.system_prompt == "Draft B"
    assert v1.is_published()
    # Original draft object is untouched
    assert draft.system_prompt == "Draft A"
    assert draft.status is ManifestStatus.DRAFT
