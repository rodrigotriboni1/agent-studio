"""US-005 API integration tests.

All tests run with AGENT_STUDIO_OFFLINE=1 (set globally in conftest or by the
caller) so no network calls, keys or databases are required.

Coverage:
  * Agents CRUD: create → get → list → update → publish → versions → rollback
  * Run: happy path (echo model returns output)
  * Governance DENIED: an agent whose ``allowed_models`` excludes its own
    primary model triggers ModelAccessDenied → HTTP 403 with ``denied`` payload
  * Ingest: POST /sources/{name}/ingest → chunks count
  * Workflows: run + resume (human-in-the-loop happy path)
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Ensure offline mode for all tests in this file.
os.environ.setdefault("AGENT_STUDIO_OFFLINE", "1")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Fresh FastAPI app with a fresh AppState for each test."""
    # Reset the singleton so each test starts with an empty store.
    import api.services as svc

    svc._singleton = None  # type: ignore[attr-defined]

    from api.main import create_app

    return create_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_HEADERS = {"X-Tenant-Id": "test-tenant"}


def create_draft(client: TestClient, **overrides) -> dict:
    payload = {
        "name": "Test Agent",
        "description": "A test agent",
        "system_prompt": "You are a test assistant.",
        "model": "echo",
        **overrides,
    }
    resp = client.post("/agents", json=payload, headers=DEFAULT_HEADERS)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Health / version smoke
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_version(client):
    resp = client.get("/version")
    assert resp.status_code == 200
    assert "version" in resp.json()


# ---------------------------------------------------------------------------
# Agents CRUD happy path
# ---------------------------------------------------------------------------


def test_create_agent(client):
    data = create_draft(client)
    assert data["status"] == "draft"
    assert data["name"] == "Test Agent"
    assert data["tenant_id"] == "test-tenant"
    assert data["version"] == 1


def test_list_agents(client):
    create_draft(client)
    create_draft(client, name="Second Agent")
    resp = client.get("/agents", headers=DEFAULT_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_agent(client):
    draft = create_draft(client)
    agent_id = draft["id"]
    resp = client.get(f"/agents/{agent_id}", headers=DEFAULT_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == agent_id


def test_get_agent_not_found(client):
    resp = client.get("/agents/nonexistent", headers=DEFAULT_HEADERS)
    assert resp.status_code == 404


def test_update_agent(client):
    draft = create_draft(client)
    agent_id = draft["id"]
    resp = client.put(
        f"/agents/{agent_id}",
        json={"name": "Updated Name", "description": "Updated desc"},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated desc"


def test_publish_agent(client):
    draft = create_draft(client)
    agent_id = draft["id"]

    resp = client.post(f"/agents/{agent_id}/publish", headers=DEFAULT_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "published"
    assert data["version"] >= 1


def test_versions_after_publish(client):
    draft = create_draft(client)
    agent_id = draft["id"]

    # Publish once.
    client.post(f"/agents/{agent_id}/publish", headers=DEFAULT_HEADERS)
    # Publish again (another version).
    client.post(f"/agents/{agent_id}/publish", headers=DEFAULT_HEADERS)

    resp = client.get(f"/agents/{agent_id}/versions", headers=DEFAULT_HEADERS)
    assert resp.status_code == 200
    versions = resp.json()
    # The original draft (v1) plus two published (v1, v2 … exact numbering
    # depends on publish() — at least 2 published entries exist).
    assert len(versions) >= 2


def test_rollback(client):
    draft = create_draft(client, name="OriginalName")
    agent_id = draft["id"]

    # Publish v1.
    v1_resp = client.post(f"/agents/{agent_id}/publish", headers=DEFAULT_HEADERS)
    v1 = v1_resp.json()["version"]

    # Update and publish v2.
    client.put(f"/agents/{agent_id}", json={"name": "ChangedName"}, headers=DEFAULT_HEADERS)
    client.post(f"/agents/{agent_id}/publish", headers=DEFAULT_HEADERS)

    # Rollback to v1.
    rollback_resp = client.post(
        f"/agents/{agent_id}/rollback",
        json={"target_version": v1},
        headers=DEFAULT_HEADERS,
    )
    assert rollback_resp.status_code == 200
    rolled = rollback_resp.json()
    # Rolled-back copy has the original name and is published.
    assert rolled["name"] == "OriginalName"
    assert rolled["status"] == "published"


def test_rollback_not_found_version(client):
    draft = create_draft(client)
    agent_id = draft["id"]
    client.post(f"/agents/{agent_id}/publish", headers=DEFAULT_HEADERS)

    resp = client.post(
        f"/agents/{agent_id}/rollback",
        json={"target_version": 999},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Runs — happy path
# ---------------------------------------------------------------------------


def test_run_agent(client):
    draft = create_draft(client)
    agent_id = draft["id"]

    resp = client.post(
        f"/agents/{agent_id}/run",
        json={"message": "Hello world"},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    # EchoModelProvider echoes the last user message.
    assert "Hello world" in data["output"]
    assert isinstance(data["tool_calls"], list)
    assert isinstance(data["denied"], list)


# ---------------------------------------------------------------------------
# Governance DENIED case
# ---------------------------------------------------------------------------


def test_governance_model_denied(client):
    """Create an agent whose allowed_models does NOT include its primary model.

    ManifestAuthzProvider enforces the allow-list: model 'echo' is the
    manifest's primary model, but allowed_models=['other-model'] means
    allowed_model_set() == {'echo', 'other-model'} ... wait, allowed_model_set
    always includes the primary model.  Instead we use a DIFFERENT primary
    model (e.g. 'gpt-4o') but set allowed_models=['only-model'] — the set
    becomes {'gpt-4o', 'only-model'}.  That still allows the primary.

    The correct setup to trigger denial: set model='gpt-4o' (the primary) and
    allowed_models=['allowed-model-x'] — allowed_model_set returns
    {'gpt-4o', 'allowed-model-x'} which INCLUDES gpt-4o.  Still allowed.

    Reading the source: allowed_model_set() = {self.model, *self.allowed_models}
    — it ALWAYS includes the primary model.  The model gate in LangGraphAgentRuntime
    checks manifest.model against manifest.allowed_model_set(), so the primary
    is always permitted by default.

    To force a denial we must use a CUSTOM AuthzProvider that denies the model.
    Since we cannot inject one through the API, we instead verify the denial
    by directly testing that ModelAccessDenied is raised when the authz check
    fails, then verify the API reflects a 403 when we wire a restrictive manifest
    through the AppState singleton.

    Approach: after creating the agent via API, we directly manipulate the
    manifest in the store to set a model that the ManifestAuthzProvider will
    deny.  We do this by creating an agent with model='forbidden-model' and
    allowed_models=['only-this-model'] — allowed_model_set() returns
    {'forbidden-model', 'only-this-model'}, which still allows 'forbidden-model'.

    The ONLY way to trigger denial through the public manifest API is if
    allowed_model_set() does NOT contain manifest.model — but the helper always
    includes it.

    Therefore: we bypass the store and inject a manipulated manifest directly,
    bypassing the normal allowed_model_set semantics by using the
    ManifestAuthzProvider with a manifest_allow set that excludes the model.
    We do this inside the test by calling the runtime directly to confirm the
    403 path works, then assert the API returns 403 on the prepared agent.
    """
    import api.services as svc

    # Reset singleton to get fresh state.
    svc._singleton = None  # type: ignore[attr-defined]
    state = svc.get_app_state()

    # Build a manifest where allowed_model_set deliberately excludes the primary
    # model.  We do this by setting model='denied-model' but overriding the
    # stored manifest's allowed_models to a list that does NOT include
    # 'denied-model' — and we bypass allowed_model_set() by patching the manifest
    # after store to have the wrong allowed_model_set.

    # Simplest correct approach: create a manifest subclass whose
    # allowed_model_set() excludes the model.
    from core.manifest.schema import AgentManifest, ManifestStatus

    class _RestrictiveManifest(AgentManifest):
        def allowed_model_set(self) -> set[str]:
            # Explicitly exclude the primary model — governance will deny it.
            return {"some-other-allowed-model"}

    restrictive = _RestrictiveManifest(
        id="denied-agent",
        tenant_id="test-tenant",
        name="Denied Agent",
        model="echo",
        version=1,
        status=ManifestStatus.DRAFT,
    )
    state.manifest_store.save(restrictive)

    # Now run via the API.
    from api.main import create_app

    app = create_app()
    # Override the app state to reuse the same singleton with our injected manifest.
    client2 = TestClient(app)

    resp = client2.post(
        "/agents/denied-agent/run",
        json={"message": "trigger denial"},
        headers={"X-Tenant-Id": "test-tenant"},
    )
    # Expect 403 — model was denied.
    assert resp.status_code == 403, resp.text
    detail = resp.json()["detail"]
    assert "denied" in detail
    denied_list = detail["denied"]
    assert any("denied" in d for d in denied_list), f"Expected denial in: {denied_list}"


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


def test_ingest(client):
    resp = client.post(
        "/sources/my-source/ingest",
        json={
            "documents": [
                {"id": "doc1", "text": "Hello world this is document one."},
                {"id": "doc2", "text": "Second document with different content."},
            ]
        },
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chunks"] >= 1


def test_ingest_empty(client):
    resp = client.post(
        "/sources/empty-source/ingest",
        json={"documents": []},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["chunks"] == 0


# ---------------------------------------------------------------------------
# Workflows — run + resume (human-in-the-loop)
# ---------------------------------------------------------------------------

SIMPLE_WORKFLOW = {
    "steps": [
        {"id": "greet", "type": "agent", "prompt": "Say hello to the user."},
    ],
    "edges": [],
}

APPROVAL_WORKFLOW = {
    "steps": [
        {
            "id": "approve_step",
            "type": "human_approval",
            "prompt": "Please review and approve.",
        },
        {"id": "final", "type": "agent", "prompt": "Workflow approved, proceeding.", "terminal": True},  # noqa: E501
        {"id": "rejected", "type": "agent", "prompt": "Workflow rejected.", "terminal": True},
    ],
    "edges": [
        {"source": "approve_step", "target": "final", "when": "approved"},
        {"source": "approve_step", "target": "rejected", "when": "rejected"},
    ],
}


def test_workflow_run_simple(client):
    resp = client.post(
        "/workflows/run",
        json={"definition": SIMPLE_WORKFLOW, "inputs": {"user": "Alice"}},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "completed"
    assert data["id"]


def test_workflow_run_and_resume(client):
    # Start the workflow — should pause at human_approval.
    start_resp = client.post(
        "/workflows/run",
        json={"definition": APPROVAL_WORKFLOW, "inputs": {}},
        headers=DEFAULT_HEADERS,
    )
    assert start_resp.status_code == 200
    run_data = start_resp.json()
    assert run_data["state"] == "waiting_approval"
    run_id = run_data["id"]
    assert run_id

    # Resume with approval=True.
    resume_resp = client.post(
        f"/workflows/{run_id}/resume",
        json={"approved": True},
        headers=DEFAULT_HEADERS,
    )
    assert resume_resp.status_code == 200
    resumed = resume_resp.json()
    assert resumed["state"] == "completed"


def test_workflow_resume_not_found(client):
    resp = client.post(
        "/workflows/nonexistent-run-id/resume",
        json={"approved": True},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tenant isolation: agents created for one tenant are not visible to another
# ---------------------------------------------------------------------------


def test_tenant_isolation(client):
    create_draft(client)  # tenant = test-tenant
    resp = client.get("/agents", headers={"X-Tenant-Id": "other-tenant"})
    assert resp.status_code == 200
    # The other tenant should see zero agents.
    assert resp.json() == []
