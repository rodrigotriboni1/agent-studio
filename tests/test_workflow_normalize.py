"""The builder emits {from,to} edges + start/end pseudo-nodes; the engine wants
{source,target} between real steps. These tests lock the API-boundary adapter so
a workflow drawn in the React Flow builder runs end-to-end (and /workflows/chat
pauses/resumes correctly)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from api.workflow_defs import normalize_workflow_definition

client = TestClient(app)

# Exactly what builder/src/pages/WorkflowBuilderPage.tsx serializes.
BUILDER_DEF = {
    "steps": [
        {"id": "triage", "type": "agent", "agent_id": "a1"},
        {"id": "review", "type": "human_approval"},
        {"id": "specialist", "type": "agent", "agent_id": "a2"},
    ],
    "edges": [
        {"from": "start", "to": "triage"},
        {"from": "triage", "to": "review"},
        {"from": "review", "to": "specialist"},
        {"from": "specialist", "to": "end"},
    ],
}


def test_normalize_maps_from_to_and_drops_pseudo_edges():
    out = normalize_workflow_definition(BUILDER_DEF)
    # from/to -> source/target
    for e in out["edges"]:
        assert "from" not in e and "to" not in e
        assert "source" in e and "target" in e
    # pseudo edges touching start/end (non-step nodes) are dropped
    pairs = {(e["source"], e["target"]) for e in out["edges"]}
    assert pairs == {("triage", "review"), ("review", "specialist")}


def test_normalize_is_idempotent_on_native_defs():
    native = {
        "steps": [{"id": "a", "type": "agent"}, {"id": "b", "type": "human_approval"}],
        "edges": [{"source": "a", "target": "b"}],
    }
    assert normalize_workflow_definition(native)["edges"] == [{"source": "a", "target": "b"}]


def test_workflow_chat_runs_builder_format_end_to_end():
    # POST a builder-shaped definition; it must compile, run, and pause at the
    # human_approval step (proves the from/to + start/end def works E2E).
    r = client.post("/workflows/chat", json={"message": "triage this", "definition": BUILDER_DEF})
    assert r.status_code == 200, r.text
    body = r.json()
    approval = body["message"]["approval"]
    assert approval is not None
    assert approval["pending_step"] == "review"

    # Resume approved -> the workflow continues to completion.
    conv_id = body["conversation_id"]
    r2 = client.post(
        f"/conversations/{conv_id}/resume",
        json={"run_id": approval["run_id"], "approved": True},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["message"]["role"] == "assistant"
