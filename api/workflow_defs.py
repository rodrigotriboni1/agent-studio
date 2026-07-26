"""Adapt builder/API workflow definitions to the engine's native shape.

The builder (and the fixed chat/workflow contract) describe a graph with:
  * edges keyed ``{from, to}``
  * UI-only ``start``/``end`` pseudo-nodes that are NOT real steps

The LangGraph engine (`core/workflows/graph.py`) expects edges keyed
``{source, target}`` connecting actual step ids. This normalizer bridges the two
so a definition drawn in the React Flow builder runs unchanged end-to-end.

Idempotent: an already-native definition (``{source, target}`` edges between
steps) passes through unchanged.
"""

from __future__ import annotations

from typing import Any


def normalize_workflow_definition(definition: dict[str, Any]) -> dict[str, Any]:
    steps = definition.get("steps", []) or []
    step_ids = {s["id"] for s in steps if isinstance(s, dict) and "id" in s}

    edges: list[dict[str, Any]] = []
    for e in definition.get("edges", []) or []:
        src = e.get("source", e.get("from"))
        tgt = e.get("target", e.get("to"))
        # Drop pseudo edges touching non-step nodes (builder 'start'/'end'):
        # a step with no incoming edge becomes the entry, no outgoing becomes terminal.
        if src not in step_ids or tgt not in step_ids:
            continue
        edge = {k: v for k, v in e.items() if k not in ("from", "to")}
        edge["source"] = src
        edge["target"] = tgt
        edges.append(edge)

    return {**definition, "steps": steps, "edges": edges}
