"""Run all Agent Studio examples in sequence (US-007).

Usage:
    python -m examples.run_all

Exits 0 on success; non-zero on any failure.
"""

from __future__ import annotations

import sys
import traceback


def _section(title: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  {title}")
    print(f"{bar}\n")


def main() -> int:  # noqa: PLR0911 (early returns are fine for a CLI runner)
    """Run all demos sequentially.  Returns exit code (0 = success)."""
    failed: list[str] = []

    # ------------------------------------------------------------------
    # 1. Agent demo
    # ------------------------------------------------------------------
    _section("1 / 3  AGENT DEMO — word_count tool, offline scripted model")
    try:
        from examples.agent_demo import run as run_agent

        result = run_agent()
        print(f"Agent answer:\n  {result.output}")
        print(f"Tool calls  : {len(result.tool_calls)}")
        for tc in result.tool_calls:
            print(f"  [{tc['name']}] args={tc['arguments']}  result={tc['result']!r}")
        if not result.output:
            print("ERROR: agent output is empty", file=sys.stderr)
            failed.append("agent_demo")
        else:
            print("\nAgent demo PASSED.")
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        failed.append("agent_demo")

    # ------------------------------------------------------------------
    # 2. RAG demo
    # ------------------------------------------------------------------
    _section("2 / 3  RAG DEMO — in-memory retrieval, fictional product docs")
    try:
        from examples.rag_demo import run as run_rag

        question = "What is the pricing for AcmeBot?"
        print(f"Question: {question}\n")
        rag_result = run_rag(question)
        print(f"Answer (excerpt):\n  {rag_result.answer[:200]}...")
        print(f"\nCitations : {len(rag_result.citations)}")
        for i, c in enumerate(rag_result.citations):
            title = c.metadata.get("title", c.source)
            print(f"  [{i + 1}] {title}  (score={c.score:.3f})")
        if not rag_result.citations:
            print("ERROR: RAG returned no citations", file=sys.stderr)
            failed.append("rag_demo")
        else:
            print("\nRAG demo PASSED.")
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        failed.append("rag_demo")

    # ------------------------------------------------------------------
    # 3. Workflow demo
    # ------------------------------------------------------------------
    _section("3 / 3  WORKFLOW DEMO — triage → specialist → human_review")
    try:
        from core.workflows import WorkflowState
        from examples.workflow_demo import _TICKET
        from examples.workflow_demo import run as run_workflow

        print(f"Ticket: {_TICKET[:80]}...\n")
        wf_run = run_workflow()
        print(f"Final state : {wf_run.state}")
        print(f"Final output: {wf_run.output}")
        print(f"History steps: {len(wf_run.history)}")
        for entry in wf_run.history:
            step = entry.get("step", "?")
            step_type = entry.get("type", "?")
            detail = entry.get("output", entry.get("approved", entry.get("outcome", "")))
            print(f"  [{step_type}] {step}: {detail!r}")
        if wf_run.state is not WorkflowState.COMPLETED:
            print(
                f"ERROR: workflow did not complete (state={wf_run.state})",
                file=sys.stderr,
            )
            failed.append("workflow_demo")
        else:
            print("\nWorkflow demo PASSED.")
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        failed.append("workflow_demo")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _section("SUMMARY")
    total = 3
    passed = total - len(failed)
    print(f"Passed: {passed} / {total}")
    if failed:
        print(f"Failed: {failed}", file=sys.stderr)
        return 1
    print("All examples ran successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
