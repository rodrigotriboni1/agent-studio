"""Workflows: multi-step / multi-agent graphs with human-in-the-loop (spec §5.3).

CONTRACT (implemented by story 5.3). A workflow is a LangGraph of steps; each
step may run an agent (via the runtime), branch on a condition, or PAUSE for
human approval (durable interrupt → resume). Concrete implementation lives in
``core/workflows/graph.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from seams.tenancy import TenantContext


class WorkflowState(StrEnum):
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowRun:
    id: str
    state: WorkflowState
    output: Any = None
    pending_step: str | None = None          # step awaiting human approval
    history: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class WorkflowEngine(Protocol):
    def start(
        self,
        definition: dict[str, Any],
        inputs: dict[str, Any],
        *,
        tenant: TenantContext | None = None,
    ) -> WorkflowRun:
        ...

    def resume(
        self,
        run_id: str,
        approval: dict[str, Any],
        *,
        tenant: TenantContext | None = None,
    ) -> WorkflowRun:
        """Resume a run paused at a human-in-the-loop step."""
        ...


__all__ = ["WorkflowState", "WorkflowRun", "WorkflowEngine"]
