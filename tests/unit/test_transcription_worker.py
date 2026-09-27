from __future__ import annotations

from io import BytesIO
from uuid import UUID, uuid4

from saxo_ai.application.transcription_worker import ProcessNextTranscriptionJob
from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
    TranscriptionJob,
)


def sample_processing_job() -> TranscriptionJob:
    return TranscriptionJob(
        job_id=uuid4(),
        status=JobStatus.PROCESSING,
        filename="solo.wav",
        size_bytes=12,
        audio_sha256="a" * 64,
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )


class FakeQueue:
    def __init__(self, job: TranscriptionJob | None) -> None:
        self.job = job
        self.completed: list[UUID] = []
        self.failures: list[tuple[UUID, JobFailureCode, bool]] = []

    def claim_next(self) -> TranscriptionJob | None:
        job, self.job = self.job, None
        return job

    def complete(self, job_id: UUID) -> TranscriptionJob:
        self.completed.append(job_id)
        raise_if_missing = self._claimed(job_id)
        return raise_if_missing.mark_completed()

    def fail(
        self,
        job_id: UUID,
        failure_code: JobFailureCode,
        *,
        retryable: bool,
    ) -> TranscriptionJob:
        self.failures.append((job_id, failure_code, retryable))
        failed = self._claimed(job_id).mark_failed(failure_code)
        return failed.mark_queued() if retryable else failed

    def _claimed(self, job_id: UUID) -> TranscriptionJob:
        return TranscriptionJob(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            filename="solo.wav",
            size_bytes=12,
            audio_sha256="a" * 64,
            saxophone_type=SaxophoneType.ALTO,
            input_mode=InputMode.SOLO,
        )


class FakeOriginals:
    def __init__(self, content: bytes | None) -> None:
        self.content = content

    def save(self, job_id: UUID, source: BytesIO) -> None:
        self.content = source.read()

    def get(self, job_id: UUID) -> bytes | None:
        return self.content


class RecordingProcessor:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[UUID, bytes]] = []

    def process(self, job: TranscriptionJob, source: BytesIO) -> None:
        self.calls.append((job.job_id, source.read()))
        if self.fail:
            raise RuntimeError("model unavailable")


def test_worker_returns_none_when_no_job_is_available() -> None:
    processor = RecordingProcessor()
    worker = ProcessNextTranscriptionJob(
        FakeQueue(None),
        FakeOriginals(b"audio"),
        processor,
    )

    assert worker.execute() is None
    assert processor.calls == []


def test_worker_loads_original_audio_processes_and_completes_job() -> None:
    job = sample_processing_job()
    queue = FakeQueue(job)
    processor = RecordingProcessor()
    worker = ProcessNextTranscriptionJob(queue, FakeOriginals(b"original"), processor)

    result = worker.execute()

    assert result is not None
    assert result.status is JobStatus.COMPLETED
    assert processor.calls == [(job.job_id, b"original")]
    assert queue.completed == [job.job_id]
    assert queue.failures == []


def test_worker_fails_permanently_when_original_audio_is_missing() -> None:
    job = sample_processing_job()
    queue = FakeQueue(job)
    worker = ProcessNextTranscriptionJob(
        queue,
        FakeOriginals(None),
        RecordingProcessor(),
    )

    result = worker.execute()

    assert result is not None
    assert result.status is JobStatus.FAILED
    assert result.failure_code is JobFailureCode.SOURCE_AUDIO_MISSING
    assert queue.failures == [
        (job.job_id, JobFailureCode.SOURCE_AUDIO_MISSING, False)
    ]


def test_worker_requeues_retryable_processing_error() -> None:
    job = sample_processing_job()
    queue = FakeQueue(job)
    worker = ProcessNextTranscriptionJob(
        queue,
        FakeOriginals(b"original"),
        RecordingProcessor(fail=True),
    )

    result = worker.execute()

    assert result is not None
    assert result.status is JobStatus.QUEUED
    assert queue.failures == [(job.job_id, JobFailureCode.PROCESSING_ERROR, True)]
