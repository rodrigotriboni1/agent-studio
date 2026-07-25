"""Agent demo (US-007).

Defines an ``AgentManifest``, registers a ``word_count`` tool in an
``InMemoryToolProvider``, and runs the agent via ``LangGraphAgentRuntime``.

Because the offline ``EchoModelProvider`` never emits tool calls we use the
tiny ``ScriptedModelProvider`` from ``examples._offline``: the first turn
requests ``word_count``, the second turn synthesises the final answer — so the
demo shows a real tool-call loop without any API key or network.

Call ``run()`` to execute and get a ``RunResult``; the ``result.output`` is
guaranteed non-empty and ``result.tool_calls`` contains at least one entry.
"""

from __future__ import annotations

from core.manifest.schema import AgentManifest, Guardrails
from core.runtime import RunResult
from core.runtime.agent import LangGraphAgentRuntime
from examples._offline import ScriptedModelProvider
from seams.models import ModelResponse
from seams.tenancy import TenantContext, use_tenant
from seams.tools import InMemoryToolProvider, ToolSpec

# --- tenant ---------------------------------------------------------------
_TENANT = TenantContext(tenant_id="demo")

# --- tool -----------------------------------------------------------------


def _word_count(text: str) -> str:
    """Count words and characters in *text*."""
    words = len(text.split())
    chars = len(text)
    return f"{words} words, {chars} characters"


# --- manifest -------------------------------------------------------------


def _build_manifest() -> AgentManifest:
    return AgentManifest(
        id="agent-demo-001",
        tenant_id=_TENANT.tenant_id,
        name="Word-Count Agent",
        description="Demo agent that counts words in user input using a tool.",
        model="scripted-offline",
        allowed_models=["scripted-offline"],
        allowed_tools=["word_count"],
        system_prompt=(
            "You are a helpful writing assistant. "
            "Use the word_count tool to analyse the user's text, then report the result."
        ),
        guardrails=Guardrails(max_tool_calls=3, temperature=0.0),
    )


# --- offline model script --------------------------------------------------

_USER_TEXT = "The quick brown fox jumps over the lazy dog"

_SCRIPT: list[ModelResponse] = [
    # Turn 1: agent requests the word_count tool.
    ModelResponse(
        content="",
        model="scripted-offline",
        tool_calls=[
            {
                "id": "tc-001",
                "function": {
                    "name": "word_count",
                    "arguments": {"text": _USER_TEXT},
                },
            }
        ],
    ),
    # Turn 2: agent synthesises a final answer incorporating the tool result.
    ModelResponse(
        content=(
            f'The phrase "{_USER_TEXT}" contains 9 words and 43 characters '
            "(as counted by the word_count tool)."
        ),
        model="scripted-offline",
    ),
]


# --- public run() ---------------------------------------------------------


def run() -> RunResult:
    """Run the agent demo end-to-end and return the ``RunResult``.

    Guarantees:
    * ``result.output`` is non-empty.
    * ``result.tool_calls`` contains at least one ``word_count`` entry.
    """
    tools = InMemoryToolProvider()
    tools.register(
        ToolSpec(
            name="word_count",
            description="Count words and characters in the provided text.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "Text to analyse."}},
                "required": ["text"],
            },
        ),
        _word_count,
    )

    runtime = LangGraphAgentRuntime(
        model_provider=ScriptedModelProvider(_SCRIPT),
        tool_provider=tools,
    )
    manifest = _build_manifest()

    with use_tenant(_TENANT):
        result = runtime.run(manifest, _USER_TEXT, tenant=_TENANT)

    return result


# --- CLI entry point ------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("AGENT DEMO — word_count tool, offline scripted model")
    print("=" * 60)
    result = run()
    print(f"\nAgent answer:\n  {result.output}")
    print(f"\nTool calls ({len(result.tool_calls)}):")
    for tc in result.tool_calls:
        print(f"  [{tc['name']}] args={tc['arguments']}  result={tc['result']!r}")
    if result.denied:
        print(f"\nGovernance denials: {result.denied}")
    print()
