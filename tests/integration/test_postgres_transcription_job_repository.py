from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
    TranscriptionJob,
)
from saxo_ai.infrastructure.postgres_engine import build_postgres_engine
from saxo_ai.infrastructure.postgres_transcription_job_repository import (
    PostgresTranscriptionJobRepository,
)

pytestmark = pytest.mark.postgres_integration

ROOT = Path(__file__).resolve().parents[2]

testcontainers_postgres = pytest.importorskip("testcontainers.postgres")


def _migrated_engine(database_url: str) -> Engine:
    env = dict(os.environ)
    env["SAXO_DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    return build_postgres_engine(database_url)


@pytest.fixture(scope="module")
def postgres_engine() -> Iterator[Engine]:
    with testcontainers_postgres.PostgresContainer(
        "postgres:16-alpine", driver="psycopg"
    ) as container:
        engine = _migrated_engine(container.get_connection_url())
        yield engine
        engine.dispose()


def sample_job(**overrides: object) -> TranscriptionJob:
    defaults: dict[str, object] = {
        "job_id": uuid4(),
        "status": JobStatus.UPLOADED,
        "filename": "solo.wav",
        "size_bytes": 1234,
        "audio_sha256": "a" * 64,
        "saxophone_type": SaxophoneType.ALTO,
        "input_mode": InputMode.SOLO,
        "failure_code": None,
    }
    defaults.update(overrides)
    return TranscriptionJob(**defaults)  # type: ignore[arg-type]


class TestPostgresTranscriptionJobRepository:
    def test_save_then_get_round_trips(self, postgres_engine: Engine) -> None:
        repository = PostgresTranscriptionJobRepository(postgres_engine)
        job = sample_job()

        repository.save(job)
        loaded = repository.get(job.job_id)

        assert loaded == job

    def test_get_missing_job_returns_none(self, postgres_engine: Engine) -> None:
        repository = PostgresTranscriptionJobRepository(postgres_engine)

        assert repository.get(uuid4()) is None

    def test_save_is_idempotent_upsert(self, postgres_engine: Engine) -> None:
        repository = PostgresTranscriptionJobRepository(postgres_engine)
        job = sample_job()
        repository.save(job)

        failed_job = job.mark_failed(JobFailureCode.AUDIO_CONTENT_INVALID)
        repository.save(failed_job)

        loaded = repository.get(job.job_id)
        assert loaded == failed_job
        assert loaded is not None
        assert loaded.status is JobStatus.FAILED

    def test_persists_across_repository_instances(self, postgres_engine: Engine) -> None:
        job = sample_job()
        PostgresTranscriptionJobRepository(postgres_engine).save(job)

        loaded = PostgresTranscriptionJobRepository(postgres_engine).get(job.job_id)

        assert loaded == job
