from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from saxo_ai.domain.models import InputMode, JobStatus, SaxophoneType, TranscriptionJob
from saxo_ai.domain.processing import ProcessingQueueMessage
from saxo_ai.infrastructure.postgres_processing_queue import (
    PostgresTranscriptionProcessingQueue,
)
from saxo_ai.infrastructure.postgres_transcription_job_repository import (
    PostgresTranscriptionJobRepository,
)

pytestmark = pytest.mark.postgres_integration


def _save_job(engine: Engine) -> TranscriptionJob:
    job = TranscriptionJob(
        job_id=uuid4(),
        status=JobStatus.UPLOADED,
        filename="solo.wav",
        size_bytes=12,
        audio_sha256="a" * 64,
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )
    PostgresTranscriptionJobRepository(engine).save(job)
    return job


def test_queue_enqueue_is_idempotent_and_ack_removes_claimed_message(
    postgres_engine: Engine,
) -> None:
    job = _save_job(postgres_engine)
    queue = PostgresTranscriptionProcessingQueue(postgres_engine)

    queue.enqueue(job.job_id)
    queue.enqueue(job.job_id)

    message = queue.claim()
    assert message == ProcessingQueueMessage(job_id=job.job_id, attempt=1)
    assert queue.claim() is None

    assert queue.ack(message) is True
    assert queue.claim() is None


def test_retry_releases_message_and_increments_attempt(postgres_engine: Engine) -> None:
    job = _save_job(postgres_engine)
    queue = PostgresTranscriptionProcessingQueue(postgres_engine)
    queue.enqueue(job.job_id)

    first = queue.claim()
    assert first == ProcessingQueueMessage(job_id=job.job_id, attempt=1)
    assert queue.retry(first) is True

    second = queue.claim()
    assert second == ProcessingQueueMessage(job_id=job.job_id, attempt=2)
    assert queue.ack(second) is True


def test_expired_lease_rejects_stale_owner_and_allows_current_owner(
    postgres_engine: Engine,
) -> None:
    job = _save_job(postgres_engine)
    now = [datetime(2026, 9, 27, 17, 0, tzinfo=UTC)]
    queue = PostgresTranscriptionProcessingQueue(
        postgres_engine,
        lease_seconds=60,
        clock=lambda: now[0],
    )
    queue.enqueue(job.job_id)

    first = queue.claim()
    assert first == ProcessingQueueMessage(job_id=job.job_id, attempt=1)

    now[0] += timedelta(seconds=61)
    second = queue.claim()

    assert second == ProcessingQueueMessage(job_id=job.job_id, attempt=2)
    assert queue.ack(first) is False
    assert queue.retry(first) is False
    assert queue.ack(second) is True
