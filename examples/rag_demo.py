"""RAG demo (US-007).

Ingests a handful of fictional product documents into an in-memory RAG index,
retrieves the most relevant chunks for a sample question, and returns a
cited answer.

Everything runs offline — ``make_rag_index()`` picks ``InMemoryRagIndex`` when
``AGENT_STUDIO_OFFLINE=1`` (or when no ``DATABASE_URL`` is set).

Call ``run()`` to execute; returns a ``dict`` with:
  * ``"answer"``    — non-empty string built from retrieved chunks.
  * ``"citations"`` — list of ``RetrievedChunk`` objects (at least one).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.rag import Document, RetrievedChunk, make_rag_index
from seams.tenancy import TenantContext, use_tenant

# --- tenant & source name -------------------------------------------------
_TENANT = TenantContext(tenant_id="demo")
_SOURCE = "acme-product-docs"

# --- sample documents (fictional product) ---------------------------------
_DOCUMENTS: list[Document] = [
    Document(
        id="doc-overview",
        text=(
            "AcmeBot is an AI-powered customer support platform designed for "
            "small and medium businesses. It integrates with your existing helpdesk "
            "and automatically triages incoming tickets using natural-language "
            "understanding. AcmeBot can handle FAQs, escalate complex issues, and "
            "learn from resolved tickets to improve over time."
        ),
        metadata={"title": "AcmeBot Overview", "section": "overview"},
    ),
    Document(
        id="doc-pricing",
        text=(
            "AcmeBot pricing is usage-based. The Starter plan covers up to "
            "500 tickets per month at $29. The Growth plan handles up to 5 000 "
            "tickets per month at $99. Enterprise plans with unlimited tickets and "
            "dedicated support start at $499 per month. All plans include a 14-day "
            "free trial — no credit card required."
        ),
        metadata={"title": "AcmeBot Pricing", "section": "pricing"},
    ),
    Document(
        id="doc-integrations",
        text=(
            "AcmeBot integrates natively with Zendesk, Freshdesk, Intercom, and "
            "Slack. A REST API and webhook support are available for custom "
            "integrations. OAuth 2.0 is used for all third-party connections, "
            "keeping customer data secure. SDKs are available for Python, Node.js, "
            "and Go."
        ),
        metadata={"title": "AcmeBot Integrations", "section": "integrations"},
    ),
    Document(
        id="doc-security",
        text=(
            "AcmeBot is SOC 2 Type II certified and GDPR compliant. All data is "
            "encrypted at rest (AES-256) and in transit (TLS 1.3). Customer data "
            "is never used to train shared models. Role-based access control and "
            "audit logs are included in every plan."
        ),
        metadata={"title": "AcmeBot Security", "section": "security"},
    ),
]

# --- result type ----------------------------------------------------------


@dataclass
class RagDemoResult:
    """Return value of ``run()``."""

    answer: str
    citations: list[RetrievedChunk] = field(default_factory=list)


# --- public run() ---------------------------------------------------------


def run(question: str = "What is the pricing for AcmeBot?") -> RagDemoResult:
    """Ingest sample docs, retrieve relevant chunks, and return a cited answer.

    Args:
        question: the user question to answer from the docs.

    Returns:
        ``RagDemoResult`` with a non-empty ``answer`` and at least one
        ``RetrievedChunk`` in ``citations``.
    """
    index = make_rag_index()

    with use_tenant(_TENANT):
        # Ingest all sample documents into the source.
        chunk_count = index.ingest(_SOURCE, _DOCUMENTS, tenant=_TENANT)

        # Retrieve the top-3 most relevant chunks.
        chunks = index.retrieve(_SOURCE, question, top_k=3, tenant=_TENANT)

    if not chunks:
        return RagDemoResult(
            answer="No relevant information found in the knowledge base.",
            citations=[],
        )

    # Build a simple cited answer from the retrieved chunks.
    context_parts = [f"[{i + 1}] {c.text}" for i, c in enumerate(chunks)]
    context = "\n\n".join(context_parts)
    source_refs = ", ".join(
        f"[{i + 1}] {c.metadata.get('title', c.source)}" for i, c in enumerate(chunks)
    )

    answer = (
        f"Based on the AcmeBot documentation:\n\n{context}\n\n"
        f"Sources: {source_refs}\n"
        f"(Retrieved {len(chunks)} chunk(s) from {chunk_count} total ingested chunks.)"
    )

    return RagDemoResult(answer=answer, citations=chunks)


# --- CLI entry point ------------------------------------------------------

if __name__ == "__main__":
    question = "What is the pricing for AcmeBot?"
    print("=" * 60)
    print("RAG DEMO — in-memory retrieval, fictional product docs")
    print("=" * 60)
    print(f"\nQuestion: {question}\n")
    result = run(question)
    print(f"Answer:\n{result.answer}")
    print(f"\nCitations ({len(result.citations)}):")
    for i, c in enumerate(result.citations):
        title = c.metadata.get("title", c.source)
        print(f"  [{i + 1}] {title}  (score={c.score:.3f})")
    print()
