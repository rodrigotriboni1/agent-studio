"""Workflow demo (US-007).

Demonstrates a three-step triage → specialist → human_review workflow built
with ``LangGraphWorkflowEngine``:

    triage       (agent) — classify the incoming support ticket
    specialist   (agent) — draft a resolution
    human_review (human_approval) — gate the resolution before sending

In the demo the human step is *auto-approved* by calling ``engine.resume()``
with ``{"approved": True}`` immediately after ``start()`` returns
``WAITING_APPROVAL``.  This lets the whole pipeline run end-to-end without
blocking on real human input, which is required for offline CI.

Call ``run()`` to execute; returns a ``WorkflowRun`` in state ``COMPLETED``.
"""

from __future__ import annotations

from core.workflows import WorkflowRun, WorkflowState
from core.workflows.graph import LangGraphWorkflowEngine
from seams.tenancy import TenantContext, use_tenant

# --- tenant ---------------------------------------------------------------
_TENANT = TenantContext(tenant_id="demo")

# --- workflow definition --------------------------------------------------
#
# Declarative dict compiled by LangGraphWorkflowEngine into a LangGraph.
# Edges: triage → specialist → human_review.
# After approval: workflow ends (no "approved" edge → graph terminates).
# After rejection: workflow ends on the rejected branch.

_WORKFLOW_DEFINITION: dict = {
    "steps": [
        {
            "id": "triage",
            "type": "agent",
            "prompt": (
                "You are a support triage agent. Classify this ticket and "
                "decide if it needs a specialist: {ticket}"
            ),
        },
        {
            "id": "specialist",
            "type": "agent",
            "prompt": (
                "You are a specialist. The triage result was: {triage}. "
                "Draft a resolution for the original ticket: {ticket}"
            ),
            "terminal": False,
        },
        {
            "id": "human_review",
            "type": "human_approval",
            "prompt": "Please review the specialist's resolution and approve or reject.",
        },
    ],
    "edges": [
        {"source": "triage", "target": "specialist"},
        {"source": "specialist", "target": "human_review"},
        {"source": "human_review", "target": "__end__", "when": "approved"},
        {"source": "human_review", "target": "__end__", "when": "rejected"},
    ],
}

# --- sample input ---------------------------------------------------------
_TICKET = (
    "My AcmeBot integration stopped syncing with Zendesk 2 hours ago. "
    "No error messages in the UI, but tickets are piling up."
)


# --- public run() ---------------------------------------------------------


def run() -> WorkflowRun:
    """Execute the triage → specialist → human_review workflow end-to-end.

    The human_review step is auto-approved so the function always returns a
    ``WorkflowRun`` in state ``COMPLETED`` without blocking.

    Returns:
        ``WorkflowRun`` with ``state == WorkflowState.COMPLETED``.
    """
    engine = LangGraphWorkflowEngine()  # uses echo_agent_runner offline

    with use_tenant(_TENANT):
        # Start the workflow — runs until the human_approval interrupt.
        wf_run = engine.start(
            _WORKFLOW_DEFINITION,
            inputs={"ticket": _TICKET},
            tenant=_TENANT,
        )

        # Auto-approve the human_review step so the demo runs end-to-end.
        if wf_run.state is WorkflowState.WAITING_APPROVAL:
            wf_run = engine.resume(
                wf_run.id,
                approval={"approved": True, "reviewer": "auto-demo"},
                tenant=_TENANT,
            )

    return wf_run


# --- CLI entry point ------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("WORKFLOW DEMO — triage → specialist → human_review")
    print("=" * 60)
    print(f"\nInput ticket:\n  {_TICKET}\n")

    wf_run = run()

    print(f"Final state : {wf_run.state}")
    print(f"Final output: {wf_run.output}")
    print(f"\nHistory ({len(wf_run.history)} steps):")
    for entry in wf_run.history:
        step = entry.get("step", entry.get("step", "?"))
        step_type = entry.get("type", "?")
        detail = entry.get("output", entry.get("approved", entry.get("outcome", "")))
        print(f"  [{step_type}] {step}: {detail!r}")
    print()
