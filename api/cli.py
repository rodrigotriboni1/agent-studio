"""agent-studio CLI (Typer).

v0: version + serve.
US-006: agent create/list/show/run, source ingest, versions list/diff/rollback.

Sub-app layout
--------------
  app
    version      -- print app version (kept from v0)
    serve        -- run the API server (kept from v0)
    agent        -- agent CRUD + run
      create
      list
      show
      run
    source       -- RAG ingestion
      ingest
    versions     -- manifest versioning (named "versions" to avoid clash with
                    the top-level "version" command)
      list
      diff
      rollback
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Annotated

import typer

# ---------------------------------------------------------------------------
# App + sub-apps
# ---------------------------------------------------------------------------

app = typer.Typer(help="agent-studio — governed agent/RAG/workflow builder.")

agent_app = typer.Typer(help="Manage agents (create, list, show, run).")
source_app = typer.Typer(help="RAG source ingestion.")
versions_app = typer.Typer(help="Manifest versioning (list, diff, rollback).")

app.add_typer(agent_app, name="agent")
app.add_typer(source_app, name="source")
app.add_typer(versions_app, name="versions")

# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

_DEFAULT_STORE = Path(os.environ.get("AGENT_STUDIO_STORE", ".agent-studio-store.json"))


def _store(store_path: Path):  # noqa: ANN201
    from core.manifest.json_store import JSONManifestStore

    return JSONManifestStore(path=store_path)


# ---------------------------------------------------------------------------
# Top-level: version + serve (v0, kept intact)
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the version."""
    from api.main import __version__

    typer.echo(__version__)


@app.command()
def serve(port: int = 8000, reload: bool = False) -> None:
    """Run the API server."""
    import uvicorn

    uvicorn.run("api.main:app", port=port, reload=reload)


# ---------------------------------------------------------------------------
# agent sub-commands
# ---------------------------------------------------------------------------

_StoreOpt = Annotated[
    Path,
    typer.Option("--store", envvar="AGENT_STUDIO_STORE", help="Path to the JSON store file."),
]
_TenantOpt = Annotated[str, typer.Option("--tenant", help="Tenant ID.")]


@agent_app.command("create")
def agent_create(
    name: Annotated[str, typer.Option("--name", help="Agent name.")],
    model: Annotated[str, typer.Option("--model", help="Model identifier.")] = "echo",
    system_prompt: Annotated[
        str,
        typer.Option("--system-prompt", help="System prompt."),
    ] = "You are a helpful assistant.",
    tool: Annotated[
        list[str] | None,
        typer.Option("--tool", help="Allowed tool name (repeatable)."),
    ] = None,
    tenant: _TenantOpt = "default",
    store: _StoreOpt = _DEFAULT_STORE,
) -> None:
    """Create a draft agent manifest and print its ID."""
    from core.manifest.schema import AgentManifest
    from seams.tenancy import TenantContext, use_tenant

    ctx = TenantContext(tenant_id=tenant)
    agent_id = str(uuid.uuid4())

    manifest = AgentManifest(
        id=agent_id,
        tenant_id=tenant,
        name=name,
        model=model,
        system_prompt=system_prompt,
        allowed_tools=list(tool) if tool else [],
    )

    with use_tenant(ctx):
        st = _store(store)
        st.save(manifest)

    typer.echo(agent_id)


@agent_app.command("list")
def agent_list(
    tenant: _TenantOpt = "default",
    store: _StoreOpt = _DEFAULT_STORE,
) -> None:
    """List all agents for a tenant."""
    from seams.tenancy import TenantContext, use_tenant

    ctx = TenantContext(tenant_id=tenant)
    with use_tenant(ctx):
        st = _store(store)
        manifests = st.list(tenant)

    if not manifests:
        typer.echo("(no agents)")
        return

    for m in manifests:
        typer.echo(f"{m.id}  {m.name!r}  model={m.model}  v{m.version}  {m.status}")


@agent_app.command("show")
def agent_show(
    agent_id: Annotated[str, typer.Argument(help="Agent ID.")],
    tenant: _TenantOpt = "default",
    store: _StoreOpt = _DEFAULT_STORE,
) -> None:
    """Show details for a single agent."""
    import json as _json

    from seams.tenancy import TenantContext, use_tenant

    ctx = TenantContext(tenant_id=tenant)
    with use_tenant(ctx):
        st = _store(store)
        try:
            m = st.get(tenant, agent_id)
        except KeyError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

    typer.echo(_json.dumps(m.model_dump(mode="json"), indent=2))


@agent_app.command("run")
def agent_run(
    agent_id: Annotated[str, typer.Argument(help="Agent ID.")],
    message: Annotated[str, typer.Option("--message", "-m", help="User message.")],
    tenant: _TenantOpt = "default",
    store: _StoreOpt = _DEFAULT_STORE,
) -> None:
    """Run an agent with a user message and print the output."""
    from core.runtime.agent import LangGraphAgentRuntime
    from seams.tenancy import TenantContext, use_tenant
    from seams.tools import InMemoryToolProvider, ToolSpec

    ctx = TenantContext(tenant_id=tenant)

    with use_tenant(ctx):
        st = _store(store)
        try:
            manifest = st.get(tenant, agent_id)
        except KeyError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

        # Shared offline tool provider with a demo echo tool.
        tool_provider = InMemoryToolProvider()
        tool_provider.register(
            ToolSpec(name="echo", description="Echo back the input."),
            lambda text="": text,
        )

        runtime = LangGraphAgentRuntime(tool_provider=tool_provider)
        result = runtime.run(manifest, message, tenant=ctx)

    typer.echo(result.output)
    if result.denied:
        for denial in result.denied:
            typer.echo(f"[denied] {denial}", err=True)


# ---------------------------------------------------------------------------
# source sub-commands
# ---------------------------------------------------------------------------


@source_app.command("ingest")
def source_ingest(
    name: Annotated[str, typer.Argument(help="Source name (used as RAG namespace).")],
    file: Annotated[
        Path | None,
        typer.Option("--file", "-f", help="Path to a .jsonl or plain-text file to ingest."),
    ] = None,
    text: Annotated[
        str | None,
        typer.Option("--text", help="Inline text to ingest."),
    ] = None,
    tenant: _TenantOpt = "default",
) -> None:
    """Ingest documents into an in-memory RAG index and print the chunk count."""
    import json as _json

    from core.rag import Document, make_rag_index
    from seams.tenancy import TenantContext, use_tenant

    if file is None and text is None:
        typer.echo("Provide --file or --text.", err=True)
        raise typer.Exit(1)

    documents: list[Document] = []

    if text:
        documents.append(Document(id=str(uuid.uuid4()), text=text))

    if file:
        raw = file.read_text(encoding="utf-8")
        if file.suffix == ".jsonl":
            for i, line in enumerate(raw.splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = _json.loads(line)
                    doc_text = obj.get("text") or obj.get("content") or str(obj)
                    doc_id = obj.get("id") or str(uuid.uuid4())
                    documents.append(Document(id=doc_id, text=doc_text))
                except _json.JSONDecodeError:
                    documents.append(Document(id=f"line-{i}", text=line))
        else:
            # Plain-text: treat whole file as one document.
            documents.append(Document(id=file.name, text=raw))

    ctx = TenantContext(tenant_id=tenant)
    with use_tenant(ctx):
        index = make_rag_index()
        chunk_count = index.ingest(name, documents, tenant=ctx)

    typer.echo(f"Ingested {chunk_count} chunk(s) into source '{name}'.")


# ---------------------------------------------------------------------------
# versions sub-commands (manifest versioning)
# ---------------------------------------------------------------------------


@versions_app.command("list")
def versions_list(
    agent_id: Annotated[str, typer.Argument(help="Agent ID.")],
    tenant: _TenantOpt = "default",
    store: _StoreOpt = _DEFAULT_STORE,
) -> None:
    """List all versions of an agent manifest."""
    from seams.tenancy import TenantContext, use_tenant

    ctx = TenantContext(tenant_id=tenant)
    with use_tenant(ctx):
        st = _store(store)
        history = st.history(tenant, agent_id)

    if not history:
        typer.echo("(no versions)")
        return

    for m in history:
        typer.echo(f"v{m.version}  {m.status}  model={m.model}")


@versions_app.command("diff")
def versions_diff(
    agent_id: Annotated[str, typer.Argument(help="Agent ID.")],
    va: Annotated[int, typer.Argument(help="Version A (before).")],
    vb: Annotated[int, typer.Argument(help="Version B (after).")],
    tenant: _TenantOpt = "default",
    store: _StoreOpt = _DEFAULT_STORE,
) -> None:
    """Diff two versions of an agent manifest."""
    import json as _json

    from core.manifest.versioning import diff
    from seams.tenancy import TenantContext, use_tenant

    ctx = TenantContext(tenant_id=tenant)
    with use_tenant(ctx):
        st = _store(store)
        try:
            ma = st.get(tenant, agent_id, version=va)
            mb = st.get(tenant, agent_id, version=vb)
        except KeyError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

    result = diff(ma, mb)
    typer.echo(_json.dumps(result, indent=2))


@versions_app.command("rollback")
def versions_rollback(
    agent_id: Annotated[str, typer.Argument(help="Agent ID.")],
    target: Annotated[int, typer.Argument(help="Version number to restore behaviour from.")],
    tenant: _TenantOpt = "default",
    store: _StoreOpt = _DEFAULT_STORE,
) -> None:
    """Roll back an agent to a previous version (publishes a new version)."""
    from core.manifest.versioning import rollback
    from seams.tenancy import TenantContext, use_tenant

    ctx = TenantContext(tenant_id=tenant)
    with use_tenant(ctx):
        st = _store(store)
        try:
            new_m = rollback(st, tenant, agent_id, target)
        except KeyError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc

    typer.echo(f"Rolled back to v{target} behaviour → new version v{new_m.version}.")


if __name__ == "__main__":
    app()
