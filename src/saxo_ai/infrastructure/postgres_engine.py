from __future__ import annotations

from sqlalchemy import Engine, create_engine


def build_postgres_engine(database_url: str) -> Engine:
    """Build a pooled, pre-ping SQLAlchemy engine for a Postgres connection URL."""

    return create_engine(database_url, pool_pre_ping=True, future=True)
