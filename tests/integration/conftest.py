from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import boto3
import pytest
from sqlalchemy import Engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer

from saxo_ai.infrastructure.object_storage_configuration import ObjectStorageSettings
from saxo_ai.infrastructure.postgres_engine import build_postgres_engine

_S3_TEST_IMAGE = "localstack/localstack:2026.08.3"
_S3_TEST_PORT = 4566
_ACCESS_KEY = "saxo-test-access"
_SECRET_KEY = "saxo-test-secret"
_BUCKET = "saxo-artifacts-test"
_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def postgres_engine() -> Iterator[Engine]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        database_url = container.get_connection_url()
        env = dict(os.environ)
        env["SAXO_DATABASE_URL"] = database_url
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=_ROOT,
            env=env,
            check=True,
        )
        engine = build_postgres_engine(database_url)
        yield engine
        engine.dispose()


@pytest.fixture(scope="module")
def object_storage_settings() -> Iterator[ObjectStorageSettings]:
    container = DockerContainer(_S3_TEST_IMAGE)
    container.with_exposed_ports(_S3_TEST_PORT)
    container.with_env("SERVICES", "s3")
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(_S3_TEST_PORT)
        endpoint_url = f"http://{host}:{port}"
        settings = ObjectStorageSettings(
            endpoint_url=endpoint_url,
            bucket=_BUCKET,
            access_key=_ACCESS_KEY,
            secret_key=_SECRET_KEY,
            region="us-east-1",
        )
        _wait_until_ready_and_create_bucket(settings)
        yield settings


def _wait_until_ready_and_create_bucket(
    settings: ObjectStorageSettings, *, attempts: int = 30
) -> None:
    client = boto3.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        region_name=settings.region,
    )
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            client.create_bucket(Bucket=settings.bucket)
            return
        except Exception as error:  # readiness probe against an external process
            last_error = error
            time.sleep(1)
    raise RuntimeError(f"S3 test service did not become ready in time: {last_error}")
