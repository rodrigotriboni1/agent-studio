"""agent-studio CLI (Typer).

v0: version + serve. Story-owned subcommands (agent create/run, ingest, versions)
are registered here as they land.
"""

from __future__ import annotations

import typer

app = typer.Typer(help="agent-studio — governed agent/RAG/workflow builder.")


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


if __name__ == "__main__":
    app()
