"""ModelProvider seam.

Rule (spec §4): the runtime NEVER talks to a concrete provider SDK. It always
speaks the OpenAI-compatible chat API through this seam, whose implementation is
`LiteLLM` today. Swapping/adding a provider or enabling BYOK becomes config, not
code.

later: this same interface points at the self-hosted **LLM Bridge** (platform
Phase 3) with zero runtime changes.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from seams.tenancy import TenantContext, current_tenant


@dataclass
class Message:
    """An OpenAI-compatible chat message."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass
class ModelResponse:
    """Normalised completion result."""

    content: str
    model: str
    raw: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class ModelProvider(Protocol):
    """OpenAI-compatible model access. All calls are tenant-scoped so BYOK /
    per-tenant credentials resolve behind the seam."""

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
        ...


class LiteLLMModelProvider:
    """Default v0 implementation: route every call through LiteLLM's
    OpenAI-compatible surface. Import of ``litellm`` is lazy so the seam can be
    imported (and stubbed in tests) without the dependency installed.

    BYOK / per-tenant keys are resolved from ``tenant.attributes['llm_keys']``
    when present; otherwise falls back to process env (LiteLLM convention).
    """

    def __init__(self, *, default_model: str = "gpt-4o-mini") -> None:
        self.default_model = default_model

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
        import litellm  # lazy

        tenant = tenant or current_tenant()
        payload = [
            {k: v for k, v in vars(m).items() if v is not None} for m in messages
        ]
        extra: dict[str, Any] = {}
        keys = tenant.attributes.get("llm_keys") if tenant else None
        if isinstance(keys, dict):
            extra["api_key"] = keys.get(model.split("/")[0])

        resp = litellm.completion(
            model=model or self.default_model,
            messages=payload,
            temperature=temperature,
            tools=tools,
            **{**extra, **kwargs},
        )
        choice = resp["choices"][0]["message"]
        return ModelResponse(
            content=choice.get("content") or "",
            model=resp.get("model", model),
            raw=dict(resp),
            tool_calls=choice.get("tool_calls") or [],
        )


class EchoModelProvider:
    """Deterministic no-network provider for tests/examples. Echoes the last
    user message so demos and CI run without any API key."""

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
        last_user = ""
        for m in messages:
            if m.role == "user":
                last_user = m.content
        return ModelResponse(content=f"[echo] {last_user}", model=model or "echo")
