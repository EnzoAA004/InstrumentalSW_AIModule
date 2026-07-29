from __future__ import annotations

import os
from collections.abc import Mapping

DATABASE_URL_ENV = "SAXO_DATABASE_URL"


class PostgresConfigurationError(ValueError):
    """Raised when Postgres connection configuration is missing or malformed."""


def load_database_url(environ: Mapping[str, str] | None = None) -> str:
    """Read the Postgres connection URL from the environment; no default is assumed."""

    values = os.environ if environ is None else environ
    raw = values.get(DATABASE_URL_ENV)
    if raw is None or not raw.strip():
        raise PostgresConfigurationError(f"{DATABASE_URL_ENV} must be set to a Postgres URL")
    if not raw.startswith("postgresql"):
        raise PostgresConfigurationError(f"{DATABASE_URL_ENV} must be a postgresql:// URL")
    return raw
