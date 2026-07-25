"""US-002 — governed LangGraph agent runtime (offline).

Every model/tool call goes through a seam; governance (manifest allow-lists +
AuthzProvider) is enforced *before* use. These tests run with no network and no
API key: the tool path is driven by a tiny scripted ``ModelProvider`` defined
here (never in ``core``), so the model→tool loop is exercised deterministically.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from core.manifest.schema import AgentManifest, Guardrails
from core.runtime import RunResult
from core.runtime.agent import LangGraphAgentRuntime, ModelAccessDenied
from seams.models import EchoModelProvider, Message, ModelResponse
from seams.tenancy import TenantContext
from seams.tools import InMemoryToolProvider, ToolSpec


class ScriptedModelProvider:
    """Offline fake: replays a fixed script of ``ModelResponse`` turns, one per
    ``complete`` call. Lets us exercise the tool-calling loop without an LLM.
    """

    def __init__(self, script: list[ModelResponse]) -> None:
        self._script = list(script)
        self.calls = 0
        self.seen_tenants: list[str | None] = []

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
        self.seen_tenants.append(tenant.tenant_id if tenant else None)
        idx = min(self.calls, len(self._script) - 1)
        self.calls += 1
        return self._script[idx]


def _tool_call(name: str, arguments: dict[str, Any], call_id: str = "c1") -> dict[str, Any]:
    """OpenAI-compatible tool-call shape the runtime understands."""
    return {"id": call_id, "function": {"name": name, "arguments": arguments}}


def _manifest(**overrides: Any) -> AgentManifest:
    base: dict[str, Any] = dict(
        id="a1",
        tenant_id="acme",
        name="Support",
        model="echo",
        allowed_models=["echo"],
    )
    base.update(overrides)
    return AgentManifest(**base)


# --------------------------------------------------------------------------
# 1. Allowed tool: model requests it, tool runs, final answer returned.
# --------------------------------------------------------------------------


def test_allowed_tool_is_invoked_and_final_answer_returned() -> None:
    side_effect: list[dict[str, Any]] = []

    tools = InMemoryToolProvider()

    def weather(city: str) -> str:
        side_effect.append({"city": city})
        return f"sunny in {city}"

    tools.register(
        ToolSpec(name="weather", description="get weather", input_schema={"type": "object"}),
        weather,
    )

    script = [
        ModelResponse(
            content="",
            model="echo",
            tool_calls=[_tool_call("weather", {"city": "Rio"})],
        ),
        ModelResponse(content="It is sunny in Rio.", model="echo"),
    ]
    runtime = LangGraphAgentRuntime(
        model_provider=ScriptedModelProvider(script),
        tool_provider=tools,
    )
    manifest = _manifest(allowed_tools=["weather"])

    result = runtime.run(manifest, "weather in Rio?", tenant=TenantContext(tenant_id="acme"))

    assert isinstance(result, RunResult)
    assert result.output == "It is sunny in Rio."
    assert result.output  # non-empty
    assert side_effect == [{"city": "Rio"}]  # tool actually ran, once
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "weather"
    assert result.tool_calls[0]["result"] == "sunny in Rio"
    assert result.denied == []


# --------------------------------------------------------------------------
# 2. Excluded tool: denied, recorded, and NEVER executed.
# --------------------------------------------------------------------------


def test_disallowed_tool_is_denied_and_never_executed() -> None:
    executed: list[str] = []

    tools = InMemoryToolProvider()

    def danger(**_: Any) -> str:
        executed.append("danger")  # side effect that must NOT happen
        return "boom"

    tools.register(ToolSpec(name="danger", description="dangerous"), danger)

    script = [
        ModelResponse(
            content="",
            model="echo",
            tool_calls=[_tool_call("danger", {})],
        ),
        ModelResponse(content="I cannot do that.", model="echo"),
    ]
    runtime = LangGraphAgentRuntime(
        model_provider=ScriptedModelProvider(script),
        tool_provider=tools,
    )
    # allow-list EXCLUDES "danger" (only "safe" allowed)
    manifest = _manifest(allowed_tools=["safe"])

    result = runtime.run(manifest, "do something dangerous", tenant=TenantContext(tenant_id="acme"))

    assert executed == []  # side effect never happened
    assert result.tool_calls == []  # nothing invoked
    assert any("danger" in d for d in result.denied)  # recorded in denials
    assert result.output == "I cannot do that."


# --------------------------------------------------------------------------
# 3. Plain echo run (no tools) — zero-arg offline defaults.
# --------------------------------------------------------------------------


def test_plain_echo_run_returns_echo_output() -> None:
    runtime = LangGraphAgentRuntime(model_provider=EchoModelProvider())
    manifest = _manifest()

    result = runtime.run(manifest, "hello world")

    assert result.output == "[echo] hello world"
    assert result.tool_calls == []
    assert result.denied == []


def test_runtime_runs_with_zero_args_offline() -> None:
    # Fully default seams (Echo + InMemory + ManifestAuthz) — no args, no network.
    runtime = LangGraphAgentRuntime()
    result = runtime.run(_manifest(), "ping")
    assert result.output == "[echo] ping"


# --------------------------------------------------------------------------
# 4. max_tool_calls guardrail stops an infinite tool loop.
# --------------------------------------------------------------------------


def test_max_tool_calls_guardrail_stops_infinite_loop() -> None:
    invocations: list[int] = []

    tools = InMemoryToolProvider()

    def loop_tool(**_: Any) -> str:
        invocations.append(1)
        return "again"

    tools.register(ToolSpec(name="loop", description="loops forever"), loop_tool)

    # Model ALWAYS asks for the tool again — a non-terminating agent.
    always_tool = ModelResponse(
        content="",
        model="echo",
        tool_calls=[_tool_call("loop", {})],
    )
    runtime = LangGraphAgentRuntime(
        model_provider=ScriptedModelProvider([always_tool]),
        tool_provider=tools,
    )
    manifest = _manifest(
        allowed_tools=["loop"],
        guardrails=Guardrails(max_tool_calls=3),
    )

    result = runtime.run(manifest, "loop forever", tenant=TenantContext(tenant_id="acme"))

    # The cap bounds tool executions; the run terminates instead of looping.
    assert len(invocations) <= 3
    assert len(result.tool_calls) <= 3
    assert isinstance(result.output, str)


# --------------------------------------------------------------------------
# 5. Model governance: disallowed model refuses the run cleanly.
# --------------------------------------------------------------------------


def test_disallowed_model_refuses_and_records_denial() -> None:
    # AuthzProvider that blocks every MODEL check — the manifest primary is
    # normally always allowed, so we deny at the seam to prove the model gate.
    from seams.authz import Decision, ResourceType

    class DenyModelAuthz:
        def check(
            self,
            *,
            resource_type: ResourceType,
            resource: str,
            manifest_allow: set[str] | None = None,
            tenant: TenantContext | None = None,
        ) -> Decision:
            if resource_type is ResourceType.MODEL:
                return Decision(allowed=False, reason="model blocked by policy")
            return Decision(allowed=True)

    runtime = LangGraphAgentRuntime(
        model_provider=EchoModelProvider(),
        authz=DenyModelAuthz(),
    )
    manifest = _manifest()

    with pytest.raises(ModelAccessDenied) as excinfo:
        runtime.run(manifest, "hi", tenant=TenantContext(tenant_id="acme"))

    # The denial is recorded on the aborted RunResult attached to the error.
    assert excinfo.value.result is not None
    assert any("model" in d for d in excinfo.value.result.denied)
