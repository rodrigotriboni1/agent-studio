"""LangGraph-backed workflow engine (spec §5.3).

A workflow is a *declarative* dict — a list of ``steps`` plus ``edges`` — that we
compile into a LangGraph ``StateGraph`` with a durable checkpointer. Step types:

    * ``agent``          — runs an injected ``agent_runner(prompt, state)`` and
                           stores its string output under the step id.
    * ``condition``      — branches: evaluates a predicate/expression over the
                           accumulated state and follows the matching edge
                           (``when: "true"`` / ``when: "false"``).
    * ``human_approval`` — a durable ``interrupt``: ``start`` runs until it hits
                           this node, then returns ``WAITING_APPROVAL`` with
                           ``pending_step`` set. ``resume`` continues from here,
                           branching on ``when: "approved"`` / ``when: "rejected"``.

The engine is decoupled from the agent runtime (US-002): it never imports
``core.runtime.agent``. Instead an ``agent_runner: Callable[[str, dict], str]``
is injected; the offline default is a deterministic echo. ``TenantContext`` is
threaded through ``start``/``resume`` (both explicit and ambient).

``import langgraph`` is guarded so importing this module never hard-fails when
the optional ``runtime`` extra is absent.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, Any, TypedDict

from core.workflows import WorkflowEngine, WorkflowRun, WorkflowState
from seams.tenancy import TenantContext, current_tenant, use_tenant

# --- guarded optional dependency -------------------------------------------
try:  # pragma: no cover - import guard
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    _LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    MemorySaver = None  # type: ignore[assignment,misc]
    StateGraph = None  # type: ignore[assignment,misc]
    START = END = None  # type: ignore[assignment]
    Command = None  # type: ignore[assignment,misc]
    interrupt = None  # type: ignore[assignment]
    _LANGGRAPH_AVAILABLE = False


AgentRunner = Callable[[str, dict[str, Any]], str]

# Sentinel edge targets meaning "end the workflow".
_END_TARGETS = frozenset({"__end__", "end", "END"})
_TRUE_BRANCHES = frozenset({"true", "yes", "approved"})
_FALSE_BRANCHES = frozenset({"false", "no", "rejected", "else"})


# --- state reducers --------------------------------------------------------
# LangGraph merges each node's returned delta into the run state via these
# reducers, so ``inputs`` persists, ``results``/``history`` accumulate and
# ``output``/``terminal`` keep the latest write across the whole graph.
def _merge_dict(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def _concat(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    return list(left or []) + list(right or [])


def _take_last(left: Any, right: Any) -> Any:
    return right if right is not None else left


class WorkflowGraphState(TypedDict, total=False):
    """The mutable state threaded through the compiled LangGraph.

    Reducers on the accumulating channels are declared via ``Annotated`` so
    ``results``/``history`` grow across nodes while ``inputs`` persists.
    """

    inputs: dict[str, Any]
    results: Annotated[dict[str, Any], _merge_dict]
    history: Annotated[list[dict[str, Any]], _concat]
    output: Annotated[Any, _take_last]
    terminal: Annotated[Any, _take_last]
    tenant_id: str


def echo_agent_runner(prompt: str, state: dict[str, Any]) -> str:
    """Deterministic, offline default agent runner (no model, no network)."""
    return f"[echo] {prompt}"


def _predicate_result(step: dict[str, Any], state: dict[str, Any]) -> bool:
    """Evaluate a ``condition`` step over ``state`` → bool.

    Supports either an injected ``predicate`` callable (``predicate(state)->bool``)
    or a safe ``expression`` string evaluated against the state values (the state
    dict is exposed as locals; no builtins).
    """
    predicate = step.get("predicate")
    if callable(predicate):
        return bool(predicate(state))
    expression = step.get("expression")
    if isinstance(expression, str):
        return bool(eval(expression, {"__builtins__": {}}, dict(state)))  # noqa: S307
    # No predicate/expression declared → treat as truthy (linear pass-through).
    return True


class LangGraphWorkflowEngine(WorkflowEngine):
    """A ``WorkflowEngine`` that compiles declarative dicts into LangGraph.

    Args:
        agent_runner: injected ``(prompt, state) -> str`` used by ``agent`` steps.
            Defaults to the deterministic offline echo runner.
        checkpointer: durable LangGraph checkpointer. Defaults to ``MemorySaver``
            so state persists across ``start``/``resume`` in-process.
    """

    def __init__(
        self,
        agent_runner: AgentRunner | None = None,
        *,
        checkpointer: Any = None,
    ) -> None:
        if not _LANGGRAPH_AVAILABLE:  # pragma: no cover - import guard
            raise RuntimeError(
                "LangGraphWorkflowEngine requires the optional 'runtime' extra "
                "(pip install 'agent-studio[runtime]')."
            )
        self._agent_runner: AgentRunner = agent_runner or echo_agent_runner
        self._checkpointer = checkpointer if checkpointer is not None else MemorySaver()
        # run_id -> declarative definition, so resume can reload the same graph.
        self._definitions: dict[str, dict[str, Any]] = {}
        self._tenants: dict[str, TenantContext] = {}

    # -- public API ---------------------------------------------------------
    def start(
        self,
        definition: dict[str, Any],
        inputs: dict[str, Any],
        *,
        tenant: TenantContext | None = None,
    ) -> WorkflowRun:
        ctx = tenant or current_tenant()
        run_id = str(uuid.uuid4())
        self._definitions[run_id] = definition
        self._tenants[run_id] = ctx

        app = self._compile(definition)
        config = self._config(run_id, ctx)
        initial: dict[str, Any] = {
            "inputs": dict(inputs),
            "results": {},
            "history": [],
            "tenant_id": ctx.tenant_id,
            "output": None,
            "terminal": None,
        }
        with use_tenant(ctx):
            result = app.invoke(initial, config)
        return self._materialize(run_id, app, config, result)

    def resume(
        self,
        run_id: str,
        approval: dict[str, Any],
        *,
        tenant: TenantContext | None = None,
    ) -> WorkflowRun:
        if run_id not in self._definitions:
            raise KeyError(f"unknown workflow run: {run_id}")
        ctx = tenant or self._tenants.get(run_id) or current_tenant()
        app = self._compile(self._definitions[run_id])
        config = self._config(run_id, ctx)
        with use_tenant(ctx):
            result = app.invoke(Command(resume=approval), config)
        return self._materialize(run_id, app, config, result)

    # -- graph construction -------------------------------------------------
    def _compile(self, definition: dict[str, Any]) -> Any:
        steps: list[dict[str, Any]] = list(definition.get("steps", []))
        edges: list[dict[str, Any]] = list(definition.get("edges", []))
        if not steps:
            raise ValueError("workflow definition must declare at least one step")

        graph = StateGraph(WorkflowGraphState)
        for step in steps:
            graph.add_node(step["id"], self._make_node(step))
        graph.add_edge(START, steps[0]["id"])

        # Group edges by source so branching steps get conditional routing.
        outgoing: dict[str, list[dict[str, Any]]] = {}
        for edge in edges:
            outgoing.setdefault(edge["source"], []).append(edge)

        for step in steps:
            sid = step["id"]
            step_edges = outgoing.get(sid, [])
            step_type = step.get("type", "agent")
            if step_type in ("condition", "human_approval") and self._is_branching(step_edges):
                self._wire_branch(graph, step, step_edges)
            elif step_edges:
                for edge in step_edges:
                    graph.add_edge(sid, self._resolve_target(edge["target"]))
            else:
                # No declared outgoing edge → this step terminates the workflow.
                graph.add_edge(sid, END)

        return graph.compile(checkpointer=self._checkpointer)

    @staticmethod
    def _is_branching(step_edges: list[dict[str, Any]]) -> bool:
        return any("when" in edge for edge in step_edges)

    def _wire_branch(
        self,
        graph: Any,
        step: dict[str, Any],
        step_edges: list[dict[str, Any]],
    ) -> None:
        """Wire a branching step (condition / human_approval) to true/false targets."""
        sid = step["id"]
        true_target: Any = END
        false_target: Any = END
        for edge in step_edges:
            branch = str(edge.get("when", "true")).lower()
            target = self._resolve_target(edge["target"])
            if branch in _TRUE_BRANCHES:
                true_target = target
            elif branch in _FALSE_BRANCHES:
                false_target = target
        mapping = {"true": true_target, "false": false_target}
        step_type = step.get("type", "agent")

        if step_type == "human_approval":
            def _router(state: dict[str, Any], _sid: str = sid) -> str:
                decision = state.get("results", {}).get(_sid, {})
                approved = bool(decision.get("approved")) if isinstance(decision, dict) else False
                return "true" if approved else "false"
        else:  # condition
            def _router(state: dict[str, Any], _step: dict[str, Any] = step) -> str:
                return "true" if _predicate_result(_step, state) else "false"

        graph.add_conditional_edges(sid, _router, mapping)

    @staticmethod
    def _resolve_target(target: str) -> Any:
        return END if target in _END_TARGETS else target

    def _make_node(self, step: dict[str, Any]) -> Callable[[dict[str, Any]], dict[str, Any]]:
        # Nodes return only their own delta; the state reducers accumulate
        # ``results``/``history`` and keep ``inputs`` across the whole graph.
        step_type = step.get("type", "agent")
        step_id = step["id"]

        if step_type == "human_approval":
            def _human_node(_state: dict[str, Any]) -> dict[str, Any]:
                approval = interrupt({"step": step_id, "prompt": step.get("prompt")})
                approved = bool(approval.get("approved")) if isinstance(approval, dict) else False
                return {
                    "results": {step_id: {"approved": approved, "approval": approval}},
                    "history": [
                        {"step": step_id, "type": "human_approval", "approved": approved}
                    ],
                }

            return _human_node

        if step_type == "condition":
            def _condition_node(state: dict[str, Any]) -> dict[str, Any]:
                outcome = _predicate_result(step, state)
                return {
                    "results": {step_id: outcome},
                    "history": [{"step": step_id, "type": "condition", "outcome": outcome}],
                }

            return _condition_node

        # default: "agent"
        def _agent_node(state: dict[str, Any]) -> dict[str, Any]:
            prompt = self._render_prompt(step, state)
            output = self._agent_runner(prompt, state)
            update: dict[str, Any] = {
                "results": {step_id: output},
                "history": [{"step": step_id, "type": "agent", "output": output}],
                "output": output,
            }
            # A terminal agent step stamps a distinct terminal output/marker.
            if step.get("terminal"):
                update["terminal"] = output
            return update

        return _agent_node

    @staticmethod
    def _render_prompt(step: dict[str, Any], state: dict[str, Any]) -> str:
        prompt = step.get("prompt", step["id"])
        if not isinstance(prompt, str):
            return str(prompt)
        # Best-effort templating over inputs + prior results; never raise.
        context: dict[str, Any] = {}
        context.update(state.get("inputs", {}))
        context.update(state.get("results", {}))
        try:
            return prompt.format(**context)
        except (KeyError, IndexError, ValueError):
            return prompt

    # -- result materialization --------------------------------------------
    def _config(self, run_id: str, ctx: TenantContext) -> dict[str, Any]:
        # Namespace the checkpoint thread by tenant so runs never collide.
        return {"configurable": {"thread_id": ctx.namespaced(run_id)}}

    def _materialize(
        self,
        run_id: str,
        app: Any,
        config: dict[str, Any],
        result: dict[str, Any],
    ) -> WorkflowRun:
        snapshot = app.get_state(config)
        history = list(result.get("history", []))

        # Paused at a human_approval interrupt?
        interrupts = getattr(snapshot, "interrupts", ())
        if interrupts:
            pending = None
            value = interrupts[0].value
            if isinstance(value, dict):
                pending = value.get("step")
            if pending is None and snapshot.next:
                pending = snapshot.next[0]
            return WorkflowRun(
                id=run_id,
                state=WorkflowState.WAITING_APPROVAL,
                output=result.get("output"),
                pending_step=pending,
                history=history,
            )

        # Terminal. A ``terminal`` marker (set by a reject/terminal branch) wins
        # so approve vs reject produce distinguishable outputs.
        output = result.get("terminal")
        if output is None:
            output = result.get("output")
        return WorkflowRun(
            id=run_id,
            state=WorkflowState.COMPLETED,
            output=output,
            pending_step=None,
            history=history,
        )


__all__ = ["LangGraphWorkflowEngine", "echo_agent_runner", "AgentRunner"]
