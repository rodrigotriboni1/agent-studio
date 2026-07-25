"""RagIndex selection (spec §5.2).

``make_rag_index`` picks the concrete RagIndex for the current environment,
defaulting to the OFFLINE, dependency-free ``InMemoryRagIndex`` and only using
the pgvector engine when a real database and its dependencies are available.

Selection rules — offline wins in every ambiguous case so CI stays green:
  * ``AGENT_STUDIO_OFFLINE=1``          -> InMemoryRagIndex
  * ``DATABASE_URL`` unset/empty        -> InMemoryRagIndex
  * pgvector/llama-index import failure -> InMemoryRagIndex
  * otherwise                           -> PgVectorRagIndex
"""

from __future__ import annotations

import os

from core.rag import RagIndex
from core.rag.memory import InMemoryRagIndex


def _offline() -> bool:
    return os.environ.get("AGENT_STUDIO_OFFLINE", "0") == "1"


def make_rag_index() -> RagIndex:
    """Return the RagIndex appropriate for the current environment."""
    if _offline():
        return InMemoryRagIndex()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return InMemoryRagIndex()

    try:
        from core.rag.llamaindex_pgvector import PgVectorRagIndex
    except ImportError:
        # llama-index / pgvector / psycopg not installed — fall back offline.
        return InMemoryRagIndex()

    return PgVectorRagIndex(database_url=database_url)
