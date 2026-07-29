from __future__ import annotations

import pytest

from saxo_ai.infrastructure.postgres_configuration import (
    DATABASE_URL_ENV,
    PostgresConfigurationError,
    load_database_url,
)


class TestLoadDatabaseUrl:
    def test_reads_configured_url(self) -> None:
        url = load_database_url({DATABASE_URL_ENV: "postgresql+psycopg://user:pw@host/db"})

        assert url == "postgresql+psycopg://user:pw@host/db"

    def test_rejects_missing_variable(self) -> None:
        with pytest.raises(PostgresConfigurationError):
            load_database_url({})

    def test_rejects_blank_variable(self) -> None:
        with pytest.raises(PostgresConfigurationError):
            load_database_url({DATABASE_URL_ENV: "   "})

    def test_rejects_non_postgres_scheme(self) -> None:
        with pytest.raises(PostgresConfigurationError):
            load_database_url({DATABASE_URL_ENV: "mysql://user:pw@host/db"})
