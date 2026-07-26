"""Application settings (V1-002).

A tiny, dependency-free settings object read from the process environment (and
therefore from a ``.env`` when the process is launched with one loaded). Kept
deliberately small: no pydantic-settings dependency, just ``os.getenv`` with
sane, offline-first defaults so the API boots with zero configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_origins(raw: str) -> list[str]:
    """Parse a comma-separated CORS origin list, trimming blanks."""
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class Settings:
    """Read-only view of the environment-driven configuration.

    Attributes:
        cors_origins: allowed browser origins for CORS.
        offline: True when ``AGENT_STUDIO_OFFLINE`` is truthy (no network/keys).
        database_url: pgvector DSN when configured, else ``None`` (health=skipped).
        default_model: model used when a manifest gives no override.
        default_tenant: tenant id used when the ``X-Tenant-Id`` header is absent.
    """

    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    offline: bool = True
    database_url: str | None = None
    default_model: str = "gpt-4o-mini"
    default_tenant: str = "default"


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    """Build a fresh :class:`Settings` from the current environment.

    Read on demand (not cached) so tests can flip env vars between requests.
    """
    origins_raw = os.getenv("AGENT_STUDIO_CORS_ORIGINS", "http://localhost:5173")
    origins = _split_origins(origins_raw) or ["http://localhost:5173"]
    database_url = os.getenv("DATABASE_URL") or None
    return Settings(
        cors_origins=origins,
        offline=_truthy(os.getenv("AGENT_STUDIO_OFFLINE")),
        database_url=database_url,
        default_model=os.getenv("AGENT_STUDIO_DEFAULT_MODEL", "gpt-4o-mini"),
        default_tenant=os.getenv("AGENT_STUDIO_DEFAULT_TENANT", "default"),
    )


__all__ = ["Settings", "get_settings"]
