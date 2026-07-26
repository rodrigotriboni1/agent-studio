"""Process-singleton application state (AppState) and its FastAPI dependency.

Holds all shared, long-lived objects:
  * InMemoryManifestStore
  * InMemoryToolProvider (with a couple of demo tools pre-registered)
  * LangGraphAgentRuntime (backed by EchoModelProvider + the shared tool provider)
  * RagIndex (make_rag_index → InMemoryRagIndex under AGENT_STUDIO_OFFLINE=1)
  * LangGraphWorkflowEngine

Use ``get_app_state`` as a FastAPI dependency — every request gets the same
singleton without rebuilding it.
"""

from __future__ import annotations

import datetime

from api.chat_store import ConversationStore
from core.manifest.store import InMemoryManifestStore
from core.rag import RagIndex, make_rag_index
from core.workflows.graph import LangGraphWorkflowEngine
from seams.models import EchoModelProvider
from seams.tools import InMemoryToolProvider, ToolSpec


class AppState:
    """Singleton container for all shared application objects."""

    def __init__(self) -> None:
        # --- tool provider (shared) ----------------------------------------
        self.tool_provider = InMemoryToolProvider()
        self._register_demo_tools()

        # --- manifest store --------------------------------------------------
        self.manifest_store = InMemoryManifestStore()

        # --- runtime ---------------------------------------------------------
        # Import lazily to guard the optional langgraph dependency.
        from core.runtime.agent import LangGraphAgentRuntime

        self.runtime = LangGraphAgentRuntime(
            model_provider=EchoModelProvider(),
            tool_provider=self.tool_provider,
        )

        # --- RAG index -------------------------------------------------------
        self.rag_index: RagIndex = make_rag_index()

        # --- workflow engine -------------------------------------------------
        self.workflow_engine = LangGraphWorkflowEngine()

        # --- conversation store (tenant-scoped chat history) -----------------
        self.conversation_store = ConversationStore()

    # ------------------------------------------------------------------
    # Demo tools
    # ------------------------------------------------------------------

    def _register_demo_tools(self) -> None:
        """Register a small set of offline-safe demo tools."""
        self.tool_provider.register(
            ToolSpec(
                name="echo",
                description="Echo back the provided text unchanged.",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            ),
            lambda text: text,
        )
        self.tool_provider.register(
            ToolSpec(
                name="now",
                description="Return the current UTC timestamp as an ISO-8601 string.",
                input_schema={"type": "object", "properties": {}},
            ),
            lambda: datetime.datetime.now(datetime.UTC).isoformat(),
        )


# ---------------------------------------------------------------------------
# Process-level singleton
# ---------------------------------------------------------------------------

_singleton: AppState | None = None


def _get_singleton() -> AppState:
    global _singleton
    if _singleton is None:
        _singleton = AppState()
    return _singleton


# FastAPI dependency
def get_app_state() -> AppState:
    """FastAPI dependency — returns the process-level singleton AppState."""
    return _get_singleton()
