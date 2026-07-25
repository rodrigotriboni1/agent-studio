"""Offline scripted ModelProvider for examples (US-007).

The standard ``EchoModelProvider`` never emits tool calls, so the agent demo
cannot show tool use without a real LLM.  ``ScriptedModelProvider`` here
replays a fixed sequence of ``ModelResponse`` turns — one per ``complete``
call — making the tool-calling loop fully deterministic and network-free.

Usage::

    from examples._offline import ScriptedModelProvider
    from seams.models import ModelResponse

    provider = ScriptedModelProvider([
        ModelResponse(content="", model="demo", tool_calls=[...]),
        ModelResponse(content="Final answer.", model="demo"),
    ])

Falls back to ``EchoModelProvider`` behaviour (echo last user message) once
the script is exhausted, so the caller never needs to count turns exactly.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from seams.models import EchoModelProvider, Message, ModelResponse
from seams.tenancy import TenantContext


class ScriptedModelProvider:
    """Replay a fixed script of ``ModelResponse`` turns one per ``complete`` call.

    When the script is exhausted, falls back to echoing the last user message
    (same behaviour as ``EchoModelProvider``).

    Args:
        script: ordered list of ``ModelResponse`` objects to replay.
        model: model name to advertise in the response (default ``"scripted"``).
    """

    def __init__(self, script: list[ModelResponse], *, model: str = "scripted") -> None:
        self._script = list(script)
        self._model = model
        self._echo = EchoModelProvider()
        self.calls: int = 0

    def complete(
        self,
        *,
        model: str,
        messages: Iterable[Message],
        tenant: TenantContext | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ModelResponse:
        if self.calls < len(self._script):
            response = self._script[self.calls]
            self.calls += 1
            return response
        # Script exhausted — echo the last user message as a final answer.
        self.calls += 1
        return self._echo.complete(
            model=model or self._model,
            messages=messages,
            tenant=tenant,
            tools=tools,
            temperature=temperature,
            **kwargs,
        )


__all__ = ["ScriptedModelProvider"]
