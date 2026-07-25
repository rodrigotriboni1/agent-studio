"""US-004 workflow engine tests — offline, no network, no keys.

Exercises the LangGraph-backed engine's declarative multi-step / multi-agent /
human-in-the-loop behavior:

    * 3-step triage → specialist → human_approval PAUSES at approval,
    * resume(approve) → COMPLETED with output,
    * resume(reject)  → distinct terminal branch,
    * a conditional step branches correctly,
    * run_id persists state across start/resume (checkpointer).
"""

from __future__ import annotations

import pytest

from core.workflows import WorkflowState
from core.workflows.graph import LangGraphWorkflowEngine, echo_agent_runner
from seams.tenancy import TenantContext

pytest.importorskip("langgraph")


# --- definitions -----------------------------------------------------------
def _approval_workflow() -> dict:
    """triage → specialist → human_approval(review); approve completes,
    reject routes to a distinct terminal 'rejected' agent step."""
    return {
        "steps": [
            {"id": "triage", "type": "agent", "prompt": "triage: {ticket}"},
            {"id": "specialist", "type": "agent", "prompt": "specialist: {triage}"},
            {"id": "review", "type": "human_approval", "prompt": "approve?"},
            {"id": "resolve", "type": "agent", "prompt": "resolved", "terminal": True},
            {"id": "reject", "type": "agent", "prompt": "rejected-and-escalated",
             "terminal": True},
        ],
        "edges": [
            {"source": "triage", "target": "specialist"},
            {"source": "specialist", "target": "review"},
            {"source": "review", "target": "resolve", "when": "approved"},
            {"source": "review", "target": "reject", "when": "rejected"},
            {"source": "resolve", "target": "__end__"},
            {"source": "reject", "target": "__end__"},
        ],
    }


def _conditional_workflow() -> dict:
    """intake → condition(is_urgent) → escalate | standard (distinct outputs)."""
    return {
        "steps": [
            {"id": "intake", "type": "agent", "prompt": "intake: {ticket}"},
            {"id": "gate", "type": "condition",
             "expression": "inputs.get('priority') == 'high'"},
            {"id": "escalate", "type": "agent", "prompt": "ESCALATED", "terminal": True},
            {"id": "standard", "type": "agent", "prompt": "STANDARD", "terminal": True},
        ],
        "edges": [
            {"source": "intake", "target": "gate"},
            {"source": "gate", "target": "escalate", "when": "true"},
            {"source": "gate", "target": "standard", "when": "false"},
            {"source": "escalate", "target": "__end__"},
            {"source": "standard", "target": "__end__"},
        ],
    }


# --- human-in-the-loop -----------------------------------------------------
def test_start_pauses_at_human_approval():
    engine = LangGraphWorkflowEngine()
    run = engine.start(_approval_workflow(), {"ticket": "printer down"})
    assert run.state is WorkflowState.WAITING_APPROVAL
    assert run.pending_step == "review"
    # triage + specialist ran before the pause.
    step_ids = [h["step"] for h in run.history]
    assert step_ids == ["triage", "specialist"]


def test_resume_approve_completes_with_output():
    engine = LangGraphWorkflowEngine()
    run = engine.start(_approval_workflow(), {"ticket": "printer down"})
    assert run.state is WorkflowState.WAITING_APPROVAL

    resumed = engine.resume(run.id, {"approved": True})
    assert resumed.state is WorkflowState.COMPLETED
    assert resumed.output == "[echo] resolved"
    step_ids = [h["step"] for h in resumed.history]
    assert "review" in step_ids and "resolve" in step_ids
    assert "reject" not in step_ids


def test_resume_reject_takes_distinct_terminal_branch():
    engine = LangGraphWorkflowEngine()
    run = engine.start(_approval_workflow(), {"ticket": "printer down"})

    resumed = engine.resume(run.id, {"approved": False})
    assert resumed.state is WorkflowState.COMPLETED
    # Distinct terminal output vs the approve path.
    assert resumed.output == "[echo] rejected-and-escalated"
    step_ids = [h["step"] for h in resumed.history]
    assert "reject" in step_ids and "resolve" not in step_ids


def test_approve_and_reject_outputs_differ():
    engine = LangGraphWorkflowEngine()
    approve_run = engine.start(_approval_workflow(), {"ticket": "x"})
    approved = engine.resume(approve_run.id, {"approved": True})
    reject_run = engine.start(_approval_workflow(), {"ticket": "x"})
    rejected = engine.resume(reject_run.id, {"approved": False})
    assert approved.output != rejected.output


# --- conditional branching -------------------------------------------------
def test_conditional_true_branch():
    engine = LangGraphWorkflowEngine()
    run = engine.start(_conditional_workflow(), {"ticket": "t", "priority": "high"})
    assert run.state is WorkflowState.COMPLETED
    assert run.output == "[echo] ESCALATED"
    assert "escalate" in [h["step"] for h in run.history]


def test_conditional_false_branch():
    engine = LangGraphWorkflowEngine()
    run = engine.start(_conditional_workflow(), {"ticket": "t", "priority": "low"})
    assert run.state is WorkflowState.COMPLETED
    assert run.output == "[echo] STANDARD"
    assert "standard" in [h["step"] for h in run.history]


def test_conditional_predicate_callable():
    engine = LangGraphWorkflowEngine()
    definition = _conditional_workflow()
    definition["steps"][1] = {
        "id": "gate",
        "type": "condition",
        "predicate": lambda state: state["inputs"]["score"] > 10,
    }
    run = engine.start(definition, {"ticket": "t", "score": 42})
    assert run.output == "[echo] ESCALATED"


# --- persistence / checkpointer -------------------------------------------
def test_run_id_persists_state_across_start_and_resume():
    engine = LangGraphWorkflowEngine()
    run = engine.start(_approval_workflow(), {"ticket": "keep-me"})
    run_id = run.id
    # A brand-new WorkflowRun instance is returned by resume, but it reuses the
    # same run_id and the checkpointer restores the pre-pause history.
    resumed = engine.resume(run_id, {"approved": True})
    assert resumed.id == run_id
    step_ids = [h["step"] for h in resumed.history]
    # History accumulated across the checkpoint boundary (pre + post pause).
    assert step_ids[:2] == ["triage", "specialist"]
    assert "resolve" in step_ids


def test_resume_unknown_run_raises():
    engine = LangGraphWorkflowEngine()
    with pytest.raises(KeyError):
        engine.resume("nope", {"approved": True})


# --- injection / tenancy ---------------------------------------------------
def test_injected_agent_runner_is_used():
    calls: list[str] = []

    def runner(prompt: str, state: dict) -> str:
        calls.append(prompt)
        return f"CUSTOM::{prompt}"

    engine = LangGraphWorkflowEngine(agent_runner=runner)
    run = engine.start(
        {
            "steps": [{"id": "solo", "type": "agent", "prompt": "hi"}],
            "edges": [{"source": "solo", "target": "__end__"}],
        },
        {},
    )
    assert run.state is WorkflowState.COMPLETED
    assert run.output == "CUSTOM::hi"
    assert calls == ["hi"]


def test_default_runner_is_offline_echo():
    assert echo_agent_runner("ping", {}) == "[echo] ping"


def test_tenant_is_threaded_and_namespaces_runs():
    seen: list[str] = []

    def runner(prompt: str, state: dict) -> str:
        seen.append(state.get("tenant_id", ""))
        return f"[echo] {prompt}"

    engine = LangGraphWorkflowEngine(agent_runner=runner)
    tenant = TenantContext(tenant_id="acme")
    run = engine.start(
        {
            "steps": [{"id": "solo", "type": "agent", "prompt": "hi"}],
            "edges": [{"source": "solo", "target": "__end__"}],
        },
        {},
        tenant=tenant,
    )
    assert run.state is WorkflowState.COMPLETED
    assert seen == ["acme"]


def test_engine_satisfies_protocol():
    from core.workflows import WorkflowEngine

    engine = LangGraphWorkflowEngine()
    assert isinstance(engine, WorkflowEngine)
