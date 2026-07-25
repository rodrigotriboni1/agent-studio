"""US-009 — Governance v0, proven end-to-end (offline, spec §5.6).

This is the *proof* that agent-studio's governance is REAL, not documentation.
Everything runs with ``AGENT_STUDIO_OFFLINE=1``: no network, no API key, no DB.
The model→tool loop is driven by a scripted ``ModelProvider`` defined in-test
(same technique US-002 used, never in ``core``), so denial is exercised
deterministically.

Four scenarios, each asserting the *side effect never happened* where a denial
is expected — a governance test that only checks a flag proves nothing:

1. TOOL DENIAL at runtime — the model asks for a tool the manifest omits; the
   tool is recorded in ``RunResult.denied`` and NEVER invoked (its side-effect
   list stays empty), while an allowed tool IS invoked. Core value prop.
2. MODEL DENIAL — a model the AuthzProvider forbids refuses the run
   (``ModelAccessDenied`` + recorded denial). See the comment on that test for
   exactly how the denial is forced.
3. TOOL DENIAL via the HTTP API — a ``TestClient`` against ``api.main.app``
   proves governance holds at the HTTP boundary: ``/run`` surfaces the denial
   and the omitted tool's side effect never fires.
4. TENANT ISOLATION — a doc ingested for tenant "acme" is invisible to tenant
   "globex"; only "acme" retrieves it. Demonstrates ``TenantContext`` namespaces
   vectors so no cross-tenant leakage is possible.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

import pytest

# Offline-first: no network / key / DB. Set before importing anything that may
# read the flag at import time (e.g. the RAG factory).
os.environ.setdefault("AGENT_STUDIO_OFFLINE", "1")

from core.manifest.schema import AgentManifest, ManifestStatus  # noqa: E402
from core.rag import Document, InMemoryRagIndex  # noqa: E402
from core.runtime import RunResult  # noqa: E402
from core.runtime.agent import LangGraphAgentRuntime, ModelAccessDenied  # noqa: E402
from seams.authz import Decision, ResourceType  # noqa: E402
from seams.models import Message, ModelResponse  # noqa: E402
from seams.tenancy import TenantContext  # noqa: E402
from seams.tools import InMemoryToolProvider, ToolSpec  # noqa: E402

# ---------------------------------------------------------------------------
# In-test scripted ModelProvider (never in core) — replays a fixed script of
# ModelResponse turns, one per ``complete`` call, so the model→tool loop runs
# deterministically without an LLM. Mirrors US-002's technique.
# ---------------------------------------------------------------------------


class ScriptedModelProvider:
    """Offline fake model: returns the next scripted ``ModelResponse`` each turn
    (clamping to the last once the script is exhausted)."""

    def __init__(self, script: list[ModelResponse]) -> None:
        self._script = list(script)
        self.calls = 0

    def complete(
        self,
        *,
        model: str,
        messages: Iterable[Message],
        tenant: TenantContext | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ModelResponse:
        idx = min(self.calls, len(self._script) - 1)
        self.calls += 1
        return self._script[idx]


def _tool_call(name: str, arguments: dict[str, Any], call_id: str = "c1") -> dict[str, Any]:
    """OpenAI-compatible tool-call shape the runtime understands."""
    return {"id": call_id, "function": {"name": name, "arguments": arguments}}


def _manifest(**overrides: Any) -> AgentManifest:
    base: dict[str, Any] = dict(
        id="gov-agent",
        tenant_id="acme",
        name="Governed Agent",
        model="echo",
        allowed_models=["echo"],
    )
    base.update(overrides)
    return AgentManifest(**base)


# ===========================================================================
# 1. TOOL DENIAL at runtime — the core value prop.
# ===========================================================================


def test_tool_denial_blocks_invocation_and_allows_permitted_tool() -> None:
    """Manifest allows only ``safe_tool``. The scripted model asks for both
    ``safe_tool`` (allowed) and ``danger_tool`` (registered but NOT allowed).

    Assertions that make this a real governance proof:
      * ``danger_tool``'s side-effect list stays EMPTY — it is never invoked.
      * ``danger_tool`` is recorded in ``RunResult.denied``.
      * ``safe_tool`` IS invoked (its side effect fires, appears in tool_calls).
    """
    safe_side_effect: list[dict[str, Any]] = []
    danger_side_effect: list[str] = []

    tools = InMemoryToolProvider()

    def safe_tool(query: str) -> str:
        safe_side_effect.append({"query": query})
        return f"safe result for {query}"

    def danger_tool(**_: Any) -> str:
        # If governance ever fails, THIS line runs and the test catches it.
        danger_side_effect.append("EXECUTED")
        return "danger executed"

    tools.register(
        ToolSpec(name="safe_tool", description="a permitted tool", input_schema={"type": "object"}),
        safe_tool,
    )
    tools.register(
        ToolSpec(name="danger_tool", description="a forbidden tool"),
        danger_tool,
    )

    # Turn 1: ask for BOTH tools in one assistant turn.
    # Turn 2: after the tool node runs, produce the final answer.
    script = [
        ModelResponse(
            content="",
            model="echo",
            tool_calls=[
                _tool_call("safe_tool", {"query": "hello"}, call_id="c1"),
                _tool_call("danger_tool", {}, call_id="c2"),
            ],
        ),
        ModelResponse(content="Done, within policy.", model="echo"),
    ]

    runtime = LangGraphAgentRuntime(
        model_provider=ScriptedModelProvider(script),
        tool_provider=tools,
    )
    # allow_tools OMITS danger_tool — only safe_tool is governed-in.
    manifest = _manifest(allowed_tools=["safe_tool"])

    result = runtime.run(
        manifest, "use the tools", tenant=TenantContext(tenant_id="acme")
    )

    assert isinstance(result, RunResult)

    # --- danger_tool: DENIED and NEVER invoked (the load-bearing assertion) ---
    assert danger_side_effect == [], "danger_tool side effect fired — governance FAILED"
    assert all(
        tc["name"] != "danger_tool" for tc in result.tool_calls
    ), "danger_tool must never appear as an executed tool call"
    assert any(
        "danger_tool" in d for d in result.denied
    ), f"danger_tool must be recorded in denials, got: {result.denied}"

    # --- safe_tool: ALLOWED and actually invoked ---
    assert safe_side_effect == [{"query": "hello"}], "safe_tool should have run exactly once"
    invoked = [tc["name"] for tc in result.tool_calls]
    assert invoked == ["safe_tool"]
    assert result.output == "Done, within policy."


# ===========================================================================
# 2. MODEL DENIAL — a forbidden model refuses the run.
# ===========================================================================


def test_model_denial_refuses_run_and_records_denial() -> None:
    """How the denial is forced:

    ``AgentManifest.allowed_model_set()`` ALWAYS includes the manifest's primary
    ``model`` (``{self.model, *self.allowed_models}``), so a plain manifest can
    never deny its own model — the ManifestAuthzProvider would always allow it.
    To mirror the runtime's real ``authz.check(MODEL, ...)`` call site while
    forcing a NEGATIVE decision, we inject a custom ``AuthzProvider`` whose MODEL
    check returns ``Decision(allowed=False)`` (equivalent to an OpenFGA/SpiceDB
    tuple that denies the model later). The runtime hits its model gate BEFORE
    building the graph, so the run refuses cleanly.
    """

    class DenyModelAuthz:
        """AuthzProvider that denies every MODEL check (allows tools/sources).

        This is exactly the shape a future FGA backend returns for a model the
        tenant is not entitled to — the runtime's call site is unchanged.
        """

        def check(
            self,
            *,
            resource_type: ResourceType,
            resource: str,
            manifest_allow: set[str] | None = None,
            tenant: TenantContext | None = None,
        ) -> Decision:
            if resource_type is ResourceType.MODEL:
                return Decision(allowed=False, reason=f"model '{resource}' not entitled")
            return Decision(allowed=True)

    runtime = LangGraphAgentRuntime(
        model_provider=ScriptedModelProvider([ModelResponse(content="hi", model="echo")]),
        authz=DenyModelAuthz(),
    )
    manifest = _manifest()

    with pytest.raises(ModelAccessDenied) as excinfo:
        runtime.run(manifest, "hello", tenant=TenantContext(tenant_id="acme"))

    # The refusal carries the aborted RunResult with the recorded denial.
    assert excinfo.value.result is not None
    assert any("model" in d for d in excinfo.value.result.denied)
    assert "echo" in excinfo.value.reason


# ===========================================================================
# 3. TOOL DENIAL via the HTTP API — governance holds at the boundary.
# ===========================================================================


def test_tool_denial_surfaces_through_the_api() -> None:
    """Prove governance at the HTTP boundary.

    We create an agent via the API whose manifest OMITS ``danger_tool``, register
    ``danger_tool`` (with a side effect) on the shared tool provider, and swap the
    singleton runtime's model for a scripted one that asks for ``danger_tool``
    (the default ``EchoModelProvider`` never requests tools). The ``/run``
    response must surface the denial and the tool must never fire.
    """
    from fastapi.testclient import TestClient

    import api.services as svc

    # Fresh singleton so we start from a clean AppState.
    svc._singleton = None  # type: ignore[attr-defined]
    state = svc.get_app_state()

    danger_side_effect: list[str] = []

    def danger_tool(**_: Any) -> str:
        danger_side_effect.append("EXECUTED")
        return "danger executed"

    state.tool_provider.register(
        ToolSpec(name="danger_tool", description="a forbidden tool"),
        danger_tool,
    )

    # Swap the shared runtime's model provider for a scripted one that requests
    # danger_tool, then falls back to a final answer. We keep the same governed
    # tool provider + ManifestAuthzProvider, so only the model script changes.
    script = [
        ModelResponse(
            content="",
            model="echo",
            tool_calls=[_tool_call("danger_tool", {}, call_id="c1")],
        ),
        ModelResponse(content="I cannot use that tool.", model="echo"),
    ]
    state.runtime.model_provider = ScriptedModelProvider(script)

    # ``api.main.app`` resolves ``get_app_state`` (our just-configured singleton)
    # per request, so the app sees the swapped model + registered danger_tool.
    from api.main import app

    client = TestClient(app)

    headers = {"X-Tenant-Id": "acme"}
    # Create an agent whose allowed_tools OMITS danger_tool (only safe_tool).
    create = client.post(
        "/agents",
        json={
            "name": "Boundary Agent",
            "model": "echo",
            "allowed_models": ["echo"],
            "allowed_tools": ["safe_tool"],
        },
        headers=headers,
    )
    assert create.status_code == 201, create.text
    agent_id = create.json()["id"]

    resp = client.post(
        f"/agents/{agent_id}/run",
        json={"message": "please use danger_tool"},
        headers=headers,
    )
    # The run itself succeeds (200) but the denial is surfaced in the body; the
    # runtime records tool denials rather than raising (only MODEL denial → 403).
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Governance held at the HTTP boundary: denial surfaced, tool never fired.
    assert danger_side_effect == [], "danger_tool ran through the API — governance FAILED"
    assert any(
        "danger_tool" in d for d in body["denied"]
    ), f"API must surface the tool denial, got: {body['denied']}"
    assert all(tc["name"] != "danger_tool" for tc in body["tool_calls"])

    # Clean up the singleton so later tests / suites get a fresh AppState.
    svc._singleton = None  # type: ignore[attr-defined]


def test_model_denial_surfaces_as_403_through_the_api() -> None:
    """Companion to the tool-denial API test: a MODEL denial is a hard refusal
    surfaced as HTTP 403 with the ``denied`` payload.

    We save a manifest whose ``allowed_model_set()`` excludes its primary model
    (via a subclass) directly into the store — the only way to make the
    ManifestAuthzProvider deny a model through the public store — then run it.
    """
    from fastapi.testclient import TestClient

    import api.services as svc

    svc._singleton = None  # type: ignore[attr-defined]
    state = svc.get_app_state()

    class _RestrictiveManifest(AgentManifest):
        def allowed_model_set(self) -> set[str]:
            # Deliberately exclude the primary model → ManifestAuthzProvider denies.
            return {"some-other-model"}

    restrictive = _RestrictiveManifest(
        id="denied-agent",
        tenant_id="acme",
        name="Denied Agent",
        model="echo",
        version=1,
        status=ManifestStatus.DRAFT,
    )
    state.manifest_store.save(restrictive)

    from api.main import app

    client = TestClient(app)
    resp = client.post(
        "/agents/denied-agent/run",
        json={"message": "trigger denial"},
        headers={"X-Tenant-Id": "acme"},
    )
    assert resp.status_code == 403, resp.text
    detail = resp.json()["detail"]
    assert any("model" in d for d in detail["denied"]), detail

    svc._singleton = None  # type: ignore[attr-defined]


# ===========================================================================
# 4. TENANT ISOLATION — vectors are namespaced by TenantContext.
# ===========================================================================


def test_tenant_isolation_prevents_cross_tenant_retrieval() -> None:
    """Ingest a doc for tenant "acme"; retrieving as "globex" returns ZERO
    results (no leakage), while "acme" retrieves it. Proves ``TenantContext``
    namespaces the vector store per tenant."""
    index = InMemoryRagIndex()

    acme = TenantContext(tenant_id="acme")
    globex = TenantContext(tenant_id="globex")

    added = index.ingest(
        "handbook",
        [Document(id="secret-1", text="Acme confidential launch codes for project falcon.")],
        tenant=acme,
    )
    assert added >= 1

    # globex queries the SAME source name but MUST see nothing from acme's data.
    leaked = index.retrieve("handbook", "falcon launch codes", tenant=globex)
    assert leaked == [], f"cross-tenant leakage: globex saw {leaked}"

    # acme retrieves its own doc.
    own = index.retrieve("handbook", "falcon launch codes", tenant=acme)
    assert own, "acme should retrieve its own ingested doc"
    assert any("falcon" in chunk.text.lower() for chunk in own)
