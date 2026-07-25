"""Agent Studio runnable examples (US-007).

Three self-contained demos that work offline with no API key:

  * agent_demo    — tool-using agent (scripted offline model shows tool use)
  * rag_demo      — in-memory RAG retrieval + cited answer
  * workflow_demo — triage → specialist → human_review workflow (auto-approved)

Run all three via:
    python -m examples.run_all
"""

from __future__ import annotations

__all__ = ["agent_demo", "rag_demo", "workflow_demo", "run_all"]
