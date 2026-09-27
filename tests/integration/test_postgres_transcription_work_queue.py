from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from saxo_ai.infrastructure.postgres_transcription_work_queue import (
    PostgresTranscriptionWorkQueue,
)

pytestmark = pytest.mark.postgres_integration


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


def sample_job() -> TranscriptionJob:
    return TranscriptionJob(
        job_id=uuid4(),
        status=JobStatus.UPLOADED,
        filename="solo.wav",
        size_bytes=1234,
        audio_sha256="a" * 64,
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )


def build_queue(
    engine: Engine,
    clock: MutableClock,
    *,
    max_attempts: int = 3,
    retry_delay: timedelta = timedelta(seconds=0),
) -> PostgresTranscriptionWorkQueue:
    return PostgresTranscriptionWorkQueue(
        engine,
        clock=clock,
        lease_duration=timedelta(minutes=1),
        max_attempts=max_attempts,
        retry_delay=retry_delay,
    )


def test_enqueue_persists_queued_job_and_claim_marks_processing(
    postgres_engine: Engine,
) -> None:
    clock = MutableClock(datetime(2026, 9, 27, 12, 0, tzinfo=UTC))
    queue = build_queue(postgres_engine, clock)
    repository = PostgresTranscriptionJobRepository(postgres_engine)
    job = sample_job()

    queued = queue.enqueue(job)
    claimed = queue.claim_next()

    assert queued.status is JobStatus.QUEUED
    assert claimed is not None
    assert claimed.job_id == job.job_id
    assert claimed.status is JobStatus.PROCESSING
    assert repository.get(job.job_id) == claimed

    completed = queue.complete(job.job_id)
    assert completed.status is JobStatus.COMPLETED
    assert repository.get(job.job_id) == completed


def test_claim_next_is_fifo_and_does_not_claim_same_live_lease_twice(
    postgres_engine: Engine,
) -> None:
    clock = MutableClock(datetime(2026, 9, 27, 12, 0, tzinfo=UTC))
    queue = build_queue(postgres_engine, clock)
    first = sample_job()
    second = sample_job()
    queue.enqueue(first)
    clock.advance(timedelta(seconds=1))
    queue.enqueue(second)

    first_claim = queue.claim_next()
    second_claim = queue.claim_next()

    assert first_claim is not None
    assert second_claim is not None
    assert first_claim.job_id == first.job_id
    assert second_claim.job_id == second.job_id

    queue.complete(first.job_id)
    queue.complete(second.job_id)


def test_expired_processing_lease_can_be_reclaimed(
    postgres_engine: Engine,
) -> None:
    clock = MutableClock(datetime(2026, 9, 27, 12, 0, tzinfo=UTC))
    queue = build_queue(postgres_engine, clock)
    job = sample_job()
    queue.enqueue(job)

    first_claim = queue.claim_next()
    assert first_claim is not None
    assert queue.claim_next() is None

    clock.advance(timedelta(minutes=1, seconds=1))
    reclaimed = queue.claim_next()

    assert reclaimed is not None
    assert reclaimed.job_id == job.job_id
    assert reclaimed.status is JobStatus.PROCESSING
    queue.complete(job.job_id)


def test_retryable_failure_is_delayed_then_becomes_terminal_at_attempt_limit(
    postgres_engine: Engine,
) -> None:
    clock = MutableClock(datetime(2026, 9, 27, 12, 0, tzinfo=UTC))
    queue = build_queue(
        postgres_engine,
        clock,
        max_attempts=2,
        retry_delay=timedelta(seconds=10),
    )
    repository = PostgresTranscriptionJobRepository(postgres_engine)
    job = sample_job()
    queue.enqueue(job)

    first_claim = queue.claim_next()
    assert first_claim is not None
    retry = queue.fail(
        job.job_id,
        JobFailureCode.PROCESSING_ERROR,
        retryable=True,
    )

    assert retry.status is JobStatus.QUEUED
    assert queue.claim_next() is None

    clock.advance(timedelta(seconds=10))
    second_claim = queue.claim_next()
    assert second_claim is not None
    failed = queue.fail(
        job.job_id,
        JobFailureCode.PROCESSING_ERROR,
        retryable=True,
    )

    assert failed.status is JobStatus.FAILED
    assert failed.failure_code is JobFailureCode.PROCESSING_ERROR
    assert repository.get(job.job_id) == failed
    assert queue.claim_next() is None
