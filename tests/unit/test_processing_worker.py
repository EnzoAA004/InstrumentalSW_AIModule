from __future__ import annotations

from io import BytesIO
from uuid import UUID

import pytest

from saxo_ai.application.processing import TranscriptionWorker
from saxo_ai.application.services import CreateTranscriptionJob
from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
)
from saxo_ai.domain.processing import ProcessingQueueMessage
from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher
from saxo_ai.infrastructure.repositories import InMemoryTranscriptionJobRepository


class RecordingOriginalAudioRepository:
    def __init__(self) -> None:
        self.saved: dict[UUID, bytes] = {}

    def save(self, job_id: UUID, source: object) -> None:
        assert hasattr(source, "read")
        self.saved[job_id] = source.read(-1)  # type: ignore[union-attr]

    def get(self, job_id: UUID) -> bytes | None:
        return self.saved.get(job_id)


class RecordingProcessingQueue:
    def __init__(self) -> None:
        self.pending: list[ProcessingQueueMessage] = []
        self.acked: list[ProcessingQueueMessage] = []
        self.retried: list[ProcessingQueueMessage] = []

    def enqueue(self, job_id: UUID) -> None:
        self.pending.append(ProcessingQueueMessage(job_id=job_id, attempt=0))

    def claim(self) -> ProcessingQueueMessage | None:
        if not self.pending:
            return None
        message = self.pending.pop(0)
        return ProcessingQueueMessage(job_id=message.job_id, attempt=message.attempt + 1)

    def ack(self, message: ProcessingQueueMessage) -> None:
        self.acked.append(message)

    def retry(self, message: ProcessingQueueMessage) -> None:
        self.retried.append(message)
        self.pending.append(message)


class RecordingProcessor:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[tuple[UUID, bytes]] = []
        self.error = error

    def process(self, job: object, source: bytes) -> None:
        job_id = job.job_id  # type: ignore[attr-defined]
        self.calls.append((job_id, source))
        if self.error is not None:
            raise self.error


def _create_queued_job() -> tuple[
    InMemoryTranscriptionJobRepository,
    RecordingOriginalAudioRepository,
    RecordingProcessingQueue,
    UUID,
]:
    jobs = InMemoryTranscriptionJobRepository()
    originals = RecordingOriginalAudioRepository()
    queue = RecordingProcessingQueue()
    use_case = CreateTranscriptionJob(
        jobs,
        Sha256AudioContentHasher(),
        original_audio_repository=originals,
        processing_queue=queue,
    )
    job = use_case.execute(
        filename="solo.wav",
        content=BytesIO(b"durable-source"),
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )
    return jobs, originals, queue, job.job_id


def test_create_job_enqueues_durable_processing_and_returns_queued_status() -> None:
    jobs, _originals, queue, job_id = _create_queued_job()

    job = jobs.get(job_id)

    assert job is not None
    assert job.status is JobStatus.QUEUED
    assert queue.pending == [ProcessingQueueMessage(job_id=job_id, attempt=0)]


def test_worker_processes_claimed_job_and_marks_it_completed() -> None:
    jobs, originals, queue, job_id = _create_queued_job()
    processor = RecordingProcessor()
    worker = TranscriptionWorker(
        jobs=jobs,
        originals=originals,
        queue=queue,
        processor=processor,
        max_attempts=3,
    )

    worked = worker.run_once()

    job = jobs.get(job_id)
    assert worked is True
    assert job is not None
    assert job.status is JobStatus.COMPLETED
    assert processor.calls == [(job_id, b"durable-source")]
    assert queue.acked == [ProcessingQueueMessage(job_id=job_id, attempt=1)]


def test_worker_requeues_failed_processing_before_max_attempts() -> None:
    jobs, originals, queue, job_id = _create_queued_job()
    worker = TranscriptionWorker(
        jobs=jobs,
        originals=originals,
        queue=queue,
        processor=RecordingProcessor(error=RuntimeError("temporary")),
        max_attempts=3,
    )

    worker.run_once()

    job = jobs.get(job_id)
    assert job is not None
    assert job.status is JobStatus.QUEUED
    assert job.failure_code is None
    assert queue.retried == [ProcessingQueueMessage(job_id=job_id, attempt=1)]
    assert queue.acked == []


def test_worker_marks_terminal_failure_after_max_attempts() -> None:
    jobs, originals, queue, job_id = _create_queued_job()
    queue.pending = [ProcessingQueueMessage(job_id=job_id, attempt=2)]
    worker = TranscriptionWorker(
        jobs=jobs,
        originals=originals,
        queue=queue,
        processor=RecordingProcessor(error=RuntimeError("permanent")),
        max_attempts=3,
    )

    worker.run_once()

    job = jobs.get(job_id)
    assert job is not None
    assert job.status is JobStatus.FAILED
    assert job.failure_code is JobFailureCode.PROCESSING_FAILED
    assert queue.acked == [ProcessingQueueMessage(job_id=job_id, attempt=3)]
    assert queue.retried == []


def test_worker_marks_missing_original_audio_as_terminal_failure() -> None:
    jobs, originals, queue, job_id = _create_queued_job()
    del originals.saved[job_id]
    worker = TranscriptionWorker(
        jobs=jobs,
        originals=originals,
        queue=queue,
        processor=RecordingProcessor(),
        max_attempts=3,
    )

    worker.run_once()

    job = jobs.get(job_id)
    assert job is not None
    assert job.status is JobStatus.FAILED
    assert job.failure_code is JobFailureCode.SOURCE_AUDIO_MISSING
    assert queue.acked == [ProcessingQueueMessage(job_id=job_id, attempt=1)]


def test_worker_returns_false_when_queue_is_empty() -> None:
    worker = TranscriptionWorker(
        jobs=InMemoryTranscriptionJobRepository(),
        originals=RecordingOriginalAudioRepository(),
        queue=RecordingProcessingQueue(),
        processor=RecordingProcessor(),
        max_attempts=3,
    )

    assert worker.run_once() is False


def test_invalid_job_state_transition_is_rejected() -> None:
    jobs, _originals, _queue, job_id = _create_queued_job()
    job = jobs.get(job_id)
    assert job is not None

    with pytest.raises(ValueError, match="cannot transition"):
        job.mark_completed()
