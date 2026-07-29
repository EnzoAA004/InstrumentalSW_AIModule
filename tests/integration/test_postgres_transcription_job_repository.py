from __future__ import annotations

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
from saxo_ai.infrastructure.postgres_transcription_job_repository import (
    PostgresTranscriptionJobRepository,
)

pytestmark = pytest.mark.postgres_integration


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
