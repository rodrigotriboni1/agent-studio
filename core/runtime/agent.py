"""LangGraph-backed, governed agent runtime (spec §5.1).

This is the concrete implementation of the ``AgentRuntime`` Protocol defined in
``core.runtime``. It executes an :class:`AgentManifest` as a minimal LangGraph:

    agent ──(model requests a tool)──▶ tools ──▶ agent ──▶ … ──▶ END

Every model call goes through the injected ``ModelProvider`` seam; every tool
call goes through the injected ``ToolProvider`` seam; and *before* either is
used, the injected ``AuthzProvider`` seam checks the resource against the
manifest allow-lists. A model that is not allowed refuses the run; a tool that is
not allowed is recorded in :attr:`RunResult.denied` and is **never invoked**.

Guardrails (temperature, ``max_tool_calls``, ``system_suffix``) come from the
manifest and are applied here. The whole run is wrapped in ``use_tenant`` so
deep seam calls read the right tenant, and the tenant is *also* passed
explicitly to every seam call.

Offline-first: the constructor defaults to zero-network seams
(:class:`EchoModelProvider`, :class:`InMemoryToolProvider`,
:class:`ManifestAuthzProvider`) so the runtime runs with no args, no key and no
network under ``AGENT_STUDIO_OFFLINE=1``. The ``langgraph`` import is guarded so
importing this module never hard-fails when the optional ``runtime`` extra is
absent — but the real ``run`` path builds and drives a LangGraph.
"""

from __future__ import annotations

from typing import Any, TypedDict

from core.manifest.schema import AgentManifest
from core.runtime import RunResult
from seams.authz import AuthzProvider, ManifestAuthzProvider, ResourceType
from seams.models import EchoModelProvider, Message, ModelProvider, ModelResponse
from seams.tenancy import TenantContext, current_tenant, use_tenant
from seams.tools import InMemoryToolProvider, ToolProvider, ToolSpec


class _AgentState(TypedDict):
    """Mutable state threaded through the LangGraph nodes."""

    messages: list[Message]
    output: str
    tool_calls: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    denied: list[str]
    tool_call_count: int
    finished: bool


class ModelAccessDenied(RuntimeError):
    """Raised when the manifest's model is not permitted by the ``AuthzProvider``.

    The refusal is also recorded on the (aborted) :class:`RunResult`, which is
    attached as :attr:`result` so callers that catch the error still see the
    governance denial.
    """

    def __init__(self, reason: str, *, result: RunResult | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.result = result


def _normalise_tool_call(call: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    """Extract ``(name, arguments, id)`` from a provider tool-call dict.

    Accepts both the flat shape ``{"name": ..., "arguments": {...}}`` and the
    OpenAI-compatible nested shape ``{"function": {"name": ..., "arguments": ...}}``.
    ``arguments`` may be a dict or a JSON string.
    """
    call_id = call.get("id")
    fn = call.get("function")
    if isinstance(fn, dict):
        name = fn.get("name", "")
        raw_args: Any = fn.get("arguments", {})
    else:
        name = call.get("name", "")
        raw_args = call.get("arguments", {})

    if isinstance(raw_args, str):
        import json

        try:
            args = json.loads(raw_args) if raw_args else {}
        except (ValueError, TypeError):
            args = {}
    elif isinstance(raw_args, dict):
        args = raw_args
    else:
        args = {}
    return name, args, call_id


class LangGraphAgentRuntime:
    """Governed agent runtime built on LangGraph.

    All model and tool access is mediated by the injected seams and gated by the
    ``AuthzProvider`` against the manifest allow-lists. Instantiate with no args
    for a fully offline, deterministic runtime.
    """

    def __init__(
        self,
        *,
        model_provider: ModelProvider | None = None,
        tool_provider: ToolProvider | None = None,
        authz: AuthzProvider | None = None,
    ) -> None:
        self.model_provider: ModelProvider = model_provider or EchoModelProvider()
        self.tool_provider: ToolProvider = tool_provider or InMemoryToolProvider()
        self.authz: AuthzProvider = authz or ManifestAuthzProvider()

    # -- governance helpers ------------------------------------------------

    def _allowed_tools(
        self,
        manifest: AgentManifest,
        tenant: TenantContext,
        denied: list[str],
    ) -> dict[str, ToolSpec]:
        """The tools the agent may actually see: intersection of what the
        provider offers, the manifest allow-list, and the AuthzProvider verdict.

        Any provider tool that the manifest/authz rejects is recorded in
        ``denied`` (once) so the caller can see governance in action.
        """
        allow_set = manifest.allowed_tool_set()
        exposed: dict[str, ToolSpec] = {}
        for spec in self.tool_provider.list_tools(tenant=tenant):
            decision = self.authz.check(
                resource_type=ResourceType.TOOL,
                resource=spec.name,
                manifest_allow=allow_set,
                tenant=tenant,
            )
            if decision.allowed:
                exposed[spec.name] = spec
            else:
                note = f"tool:{spec.name} denied ({decision.reason})"
                if note not in denied:
                    denied.append(note)
        return exposed

    def _tool_schemas(self, tools: dict[str, ToolSpec]) -> list[dict[str, Any]]:
        """OpenAI-compatible tool schemas for the allowed tools (passed to the
        model so it knows what it may call)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema
                    or {"type": "object", "properties": {}},
                },
            }
            for spec in tools.values()
        ]

    # -- run ---------------------------------------------------------------

    def run(
        self,
        manifest: AgentManifest,
        message: str,
        *,
        tenant: TenantContext | None = None,
    ) -> RunResult:
        from langgraph.graph import END, StateGraph  # guarded: real path

        tenant = tenant or current_tenant()
        guardrails = manifest.guardrails
        result = RunResult(output="")

        # --- governance: model gate (before anything else) ---------------
        model_decision = self.authz.check(
            resource_type=ResourceType.MODEL,
            resource=manifest.model,
            manifest_allow=manifest.allowed_model_set(),
            tenant=tenant,
        )
        if not model_decision.allowed:
            result.denied.append(f"model:{manifest.model} denied ({model_decision.reason})")
            raise ModelAccessDenied(model_decision.reason, result=result)

        # System prompt with guardrail suffix appended.
        system_prompt = manifest.system_prompt
        if guardrails.system_suffix:
            system_prompt = f"{system_prompt}\n\n{guardrails.system_suffix}"

        max_tool_calls = max(0, guardrails.max_tool_calls)
        temperature = guardrails.temperature

        def agent_node(state: _AgentState) -> _AgentState:
            """Call the model through the seam; decide whether to route to tools."""
            allowed = self._allowed_tools(manifest, tenant, state["denied"])
            tool_schemas = self._tool_schemas(allowed)

            response: ModelResponse = self.model_provider.complete(
                model=manifest.model,
                messages=list(state["messages"]),
                tenant=tenant,
                tools=tool_schemas or None,
                temperature=temperature,
            )
            state["steps"].append(
                {"node": "agent", "content": response.content, "tool_calls": response.tool_calls}
            )

            # If cap already hit, force a final answer regardless of the model.
            if state["tool_call_count"] >= max_tool_calls:
                state["output"] = response.content or state["output"]
                state["finished"] = True
                return state

            if response.tool_calls:
                # Keep the assistant turn (that requested the tools) in history,
                # then stash the raw calls on the step for the tools node.
                state["messages"].append(
                    Message(role="assistant", content=response.content or "")
                )
                state["steps"][-1]["_pending_calls"] = response.tool_calls
                state["finished"] = False
                return state

            state["output"] = response.content
            state["finished"] = True
            return state

        def tools_node(state: _AgentState) -> _AgentState:
            """Invoke the requested tools through the seam — governed & capped."""
            pending: list[dict[str, Any]] = state["steps"][-1].get("_pending_calls", [])
            allowed = self._allowed_tools(manifest, tenant, state["denied"])

            for call in pending:
                if state["tool_call_count"] >= max_tool_calls:
                    break
                name, args, call_id = _normalise_tool_call(call)

                # Governance: a request for a non-allowed tool is refused and the
                # tool is NEVER invoked.
                if name not in allowed:
                    decision = self.authz.check(
                        resource_type=ResourceType.TOOL,
                        resource=name,
                        manifest_allow=manifest.allowed_tool_set(),
                        tenant=tenant,
                    )
                    reason = decision.reason or "not exposed to this agent"
                    note = f"tool:{name} denied ({reason})"
                    if note not in state["denied"]:
                        state["denied"].append(note)
                    state["messages"].append(
                        Message(
                            role="tool",
                            content=f"tool '{name}' is not permitted for this agent",
                            name=name,
                            tool_call_id=call_id,
                        )
                    )
                    state["steps"].append({"node": "tools", "tool": name, "denied": True})
                    continue

                state["tool_call_count"] += 1
                tool_result = self.tool_provider.invoke(name, args, tenant=tenant)
                record = {
                    "id": call_id,
                    "name": name,
                    "arguments": args,
                    "result": tool_result.content,
                    "is_error": tool_result.is_error,
                }
                state["tool_calls"].append(record)
                state["steps"].append(
                    {"node": "tools", "tool": name, "is_error": tool_result.is_error}
                )
                state["messages"].append(
                    Message(
                        role="tool",
                        content=str(tool_result.content),
                        name=name,
                        tool_call_id=call_id,
                    )
                )
            return state

        def route_after_agent(state: _AgentState) -> str:
            if state["finished"]:
                return END
            return "tools"

        def route_after_tools(state: _AgentState) -> str:
            # Cap reached ⇒ end the loop deterministically.
            if state["tool_call_count"] >= max_tool_calls:
                return END
            return "agent"

        graph = StateGraph(_AgentState)
        graph.add_node("agent", agent_node)
        graph.add_node("tools", tools_node)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
        graph.add_conditional_edges("tools", route_after_tools, {"agent": "agent", END: END})
        compiled = graph.compile()

        initial: _AgentState = {
            "messages": [
                Message(role="system", content=system_prompt),
                Message(role="user", content=message),
            ],
            "output": "",
            "tool_calls": [],
            "steps": [],
            "denied": list(result.denied),
            "tool_call_count": 0,
            "finished": False,
        }

        # Thread the tenant ambiently for the whole graph execution (seam calls
        # also receive it explicitly). A recursion_limit backstops the cap.
        with use_tenant(tenant):
            final: _AgentState = compiled.invoke(
                initial,
                config={"recursion_limit": 2 * (max_tool_calls + 1) + 2},
            )

        result.output = final["output"]
        result.tool_calls = final["tool_calls"]
        result.steps = final["steps"]
        result.denied = final["denied"]
        return result


__all__ = ["LangGraphAgentRuntime", "ModelAccessDenied"]
