"""US-007 — smoke tests for the runnable examples.

Each test imports and calls the example's ``run()`` (or ``main()``) function
under ``AGENT_STUDIO_OFFLINE=1`` and asserts the acceptance criteria:

  * agent_demo  — non-empty output AND at least one tool call recorded.
  * rag_demo    — non-empty answer AND at least one citation returned.
  * workflow_demo — ``WorkflowRun.state`` is ``WorkflowState.COMPLETED``.
  * run_all     — ``main()`` returns exit code 0.
"""

from __future__ import annotations

import os

import pytest

# All tests require the offline flag — guard here so individual runners are
# not confused when the env var is absent.
pytestmark = pytest.mark.skipif(
    os.environ.get("AGENT_STUDIO_OFFLINE") != "1",
    reason="Set AGENT_STUDIO_OFFLINE=1 to run example smoke tests.",
)


# --------------------------------------------------------------------------
# 1. Agent demo
# --------------------------------------------------------------------------


def test_agent_demo_runs_and_returns_non_empty_output() -> None:
    """Agent demo must produce a non-empty answer and invoke the word_count tool."""
    from examples.agent_demo import run

    result = run()

    assert result.output, "Agent output must be non-empty"
    assert len(result.tool_calls) >= 1, "Agent must have invoked at least one tool"
    tool_names = [tc["name"] for tc in result.tool_calls]
    assert "word_count" in tool_names, f"Expected word_count in tool calls; got {tool_names}"


# --------------------------------------------------------------------------
# 2. RAG demo
# --------------------------------------------------------------------------


def test_rag_demo_returns_answer_with_citations() -> None:
    """RAG demo must return a non-empty answer with at least one citation."""
    from examples.rag_demo import run

    result = run("What is the pricing for AcmeBot?")

    assert result.answer, "RAG answer must be non-empty"
    assert len(result.citations) >= 1, "RAG demo must return at least one citation"
    # Each citation must have a source and a non-zero score.
    for chunk in result.citations:
        assert chunk.source, "Each citation must have a source"
        assert chunk.score > 0.0, f"Citation score must be positive; got {chunk.score}"


# --------------------------------------------------------------------------
# 3. Workflow demo
# --------------------------------------------------------------------------


def test_workflow_demo_reaches_completed() -> None:
    """Workflow demo must complete (not stall at WAITING_APPROVAL)."""
    from core.workflows import WorkflowState
    from examples.workflow_demo import run

    wf_run = run()

    assert wf_run.state is WorkflowState.COMPLETED, (
        f"Expected WorkflowState.COMPLETED, got {wf_run.state}"
    )
    assert len(wf_run.history) >= 1, "WorkflowRun must record at least one step in history"


# --------------------------------------------------------------------------
# 4. run_all
# --------------------------------------------------------------------------


def test_run_all_exits_zero() -> None:
    """run_all.main() must return 0 (all demos pass)."""
    from examples.run_all import main

    exit_code = main()

    assert exit_code == 0, f"run_all.main() returned non-zero exit code: {exit_code}"
