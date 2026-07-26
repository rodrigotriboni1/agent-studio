"""V1 chat API tests (V1-002 / V1-003 / V1-004).

All tests run offline (AGENT_STUDIO_OFFLINE=1) — EchoModelProvider, in-memory
tool/RAG/workflow, no network, no key, no DB.

Coverage:
  * two-turn agent chat keeps history (turn 2 context includes turn 1)
  * a governance-denied tool surfaces in message.denied
  * SSE stream: >=1 token event then a done event
  * GET /conversations and /conversations/{id} are tenant-scoped
  * workflow chat: human_approval pauses (approval set); resume approved ->
    COMPLETED assistant message; rejected -> rejected message
  * CORS preflight OPTIONS to /agents returns access-control-allow-origin
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

# Force offline mode for the whole module.
os.environ.setdefault("AGENT_STUDIO_OFFLINE", "1")
os.environ["AGENT_STUDIO_OFFLINE"] = "1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DEFAULT_HEADERS = {"X-Tenant-Id": "test-tenant"}


@pytest.fixture()
def app():
    import api.services as svc

    svc._singleton = None  # type: ignore[attr-defined]

    from api.main import create_app

    return create_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


def _create_agent(client: TestClient, **overrides) -> dict:
    payload = {
        "name": "Chat Agent",
        "description": "agent for chat tests",
        "system_prompt": "You are a test assistant.",
        "model": "echo",
        **overrides,
    }
    resp = client.post("/agents", json=payload, headers=DEFAULT_HEADERS)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Agent chat — two turns keep history
# ---------------------------------------------------------------------------


def test_agent_chat_two_turns_keep_history(client):
    agent = _create_agent(client)
    agent_id = agent["id"]

    # Turn 1.
    r1 = client.post(
        f"/agents/{agent_id}/chat",
        json={"message": "remember apple"},
        headers=DEFAULT_HEADERS,
    )
    assert r1.status_code == 200, r1.text
    data1 = r1.json()
    conv_id = data1["conversation_id"]
    msg1 = data1["message"]
    assert msg1["role"] == "assistant"
    assert "apple" in msg1["content"]  # echo of turn-1 message
    assert isinstance(msg1["tool_calls"], list)
    assert isinstance(msg1["denied"], list)
    assert "ts" in msg1

    # Turn 2 — same conversation. The composed context includes turn 1, and the
    # offline echo reflects it, so the earlier content is observable in turn 2.
    r2 = client.post(
        f"/agents/{agent_id}/chat",
        json={"message": "what fruit?", "conversation_id": conv_id},
        headers=DEFAULT_HEADERS,
    )
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2["conversation_id"] == conv_id
    assert "apple" in data2["message"]["content"], data2["message"]["content"]

    # The full conversation now has 4 messages (2 user + 2 assistant).
    full = client.get(f"/conversations/{conv_id}", headers=DEFAULT_HEADERS)
    assert full.status_code == 200
    assert len(full.json()["messages"]) == 4


# ---------------------------------------------------------------------------
# Governance-denied tool surfaces in message.denied
# ---------------------------------------------------------------------------


def test_agent_chat_denied_tool_surfaces(client):
    # allowed_tools=['echo'] excludes the pre-registered 'now' demo tool, which
    # the runtime therefore denies at the tool-exposure gate → RunResult.denied.
    agent = _create_agent(client, allowed_tools=["echo"])
    agent_id = agent["id"]

    resp = client.post(
        f"/agents/{agent_id}/chat",
        json={"message": "hello"},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    msg = resp.json()["message"]
    assert msg["denied"], "expected a governance denial on the assistant message"
    assert any("now" in d for d in msg["denied"]), msg["denied"]
    # The turn still produced content (denial does not abort the run here).
    assert "hello" in msg["content"]


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------


def test_agent_chat_stream_sse(client):
    agent = _create_agent(client)
    agent_id = agent["id"]

    resp = client.post(
        f"/agents/{agent_id}/chat/stream",
        json={"message": "stream these words please"},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")

    # Parse the SSE frames.
    events = []
    for block in resp.text.split("\n\n"):
        block = block.strip()
        if not block.startswith("data:"):
            continue
        events.append(json.loads(block[len("data:"):].strip()))

    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]
    assert len(token_events) >= 1, events
    assert len(done_events) == 1, events

    done = done_events[0]
    assert done["message"]["role"] == "assistant"
    assert "citations" in done["message"]
    assert "tool_calls" in done["message"]
    assert "denied" in done["message"]
    # Reassembled token text equals the assistant content.
    streamed = "".join(e["text"] for e in token_events)
    assert streamed == done["message"]["content"]


# ---------------------------------------------------------------------------
# Conversations — tenant-scoped
# ---------------------------------------------------------------------------


def test_conversations_tenant_scoped(client):
    agent = _create_agent(client)
    agent_id = agent["id"]

    # Create a conversation for test-tenant.
    r = client.post(
        f"/agents/{agent_id}/chat",
        json={"message": "hi there"},
        headers=DEFAULT_HEADERS,
    )
    conv_id = r.json()["conversation_id"]

    # Listing for the owning tenant returns it (summary has no messages).
    listed = client.get("/conversations", headers=DEFAULT_HEADERS)
    assert listed.status_code == 200
    summaries = listed.json()
    assert any(c["id"] == conv_id for c in summaries)
    assert "messages" not in summaries[0]

    # Another tenant sees nothing and cannot fetch the conversation.
    other = client.get("/conversations", headers={"X-Tenant-Id": "other-tenant"})
    assert other.status_code == 200
    assert other.json() == []

    denied = client.get(
        f"/conversations/{conv_id}", headers={"X-Tenant-Id": "other-tenant"}
    )
    assert denied.status_code == 404

    # Owning tenant fetches the full conversation with messages.
    full = client.get(f"/conversations/{conv_id}", headers=DEFAULT_HEADERS)
    assert full.status_code == 200
    body = full.json()
    assert body["id"] == conv_id
    assert body["tenant_id"] == "test-tenant"
    assert len(body["messages"]) == 2


# ---------------------------------------------------------------------------
# Workflow-driven chat + resume (human-in-the-loop)
# ---------------------------------------------------------------------------

APPROVAL_WORKFLOW = {
    "steps": [
        {"id": "approve_step", "type": "human_approval", "prompt": "Please review."},
        {"id": "final", "type": "agent", "prompt": "Approved, proceeding.", "terminal": True},
        {"id": "rejected", "type": "agent", "prompt": "Rejected.", "terminal": True},
    ],
    "edges": [
        {"source": "approve_step", "target": "final", "when": "approved"},
        {"source": "approve_step", "target": "rejected", "when": "rejected"},
    ],
}


def test_workflow_chat_approval_set(client):
    resp = client.post(
        "/workflows/chat",
        json={"message": "kick off", "definition": APPROVAL_WORKFLOW},
        headers=DEFAULT_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    msg = data["message"]
    assert msg["approval"] is not None
    assert msg["approval"]["run_id"]
    assert msg["approval"]["pending_step"] == "approve_step"
    assert msg["approval"]["resolved"] is None


def test_workflow_chat_resume_approved(client):
    start = client.post(
        "/workflows/chat",
        json={"message": "kick off", "definition": APPROVAL_WORKFLOW},
        headers=DEFAULT_HEADERS,
    )
    data = start.json()
    conv_id = data["conversation_id"]
    run_id = data["message"]["approval"]["run_id"]

    resume = client.post(
        f"/conversations/{conv_id}/resume",
        json={"run_id": run_id, "approved": True},
        headers=DEFAULT_HEADERS,
    )
    assert resume.status_code == 200, resume.text
    msg = resume.json()["message"]
    assert msg["role"] == "assistant"
    assert "Approved" in msg["content"] or "proceeding" in msg["content"]

    # The prior approval is now marked resolved='approved'.
    full = client.get(f"/conversations/{conv_id}", headers=DEFAULT_HEADERS).json()
    approvals = [m["approval"] for m in full["messages"] if m["approval"]]
    assert approvals and approvals[0]["resolved"] == "approved"


def test_workflow_chat_resume_rejected(client):
    start = client.post(
        "/workflows/chat",
        json={"message": "kick off", "definition": APPROVAL_WORKFLOW},
        headers=DEFAULT_HEADERS,
    )
    data = start.json()
    conv_id = data["conversation_id"]
    run_id = data["message"]["approval"]["run_id"]

    resume = client.post(
        f"/conversations/{conv_id}/resume",
        json={"run_id": run_id, "approved": False},
        headers=DEFAULT_HEADERS,
    )
    assert resume.status_code == 200, resume.text
    msg = resume.json()["message"]
    assert msg["role"] == "assistant"
    # Rejected content — either the workflow's rejected branch output or the note.
    assert "eject" in msg["content"].lower() or "reject" in msg["content"].lower()

    full = client.get(f"/conversations/{conv_id}", headers=DEFAULT_HEADERS).json()
    approvals = [m["approval"] for m in full["messages"] if m["approval"]]
    assert approvals and approvals[0]["resolved"] == "rejected"


# ---------------------------------------------------------------------------
# CORS preflight
# ---------------------------------------------------------------------------


def test_cors_preflight_agents(client):
    resp = client.options(
        "/agents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Tenant-Id",
        },
    )
    assert resp.status_code in (200, 204), resp.text
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
