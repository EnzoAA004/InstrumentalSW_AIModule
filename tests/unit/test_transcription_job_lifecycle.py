from __future__ import annotations

from uuid import uuid4

import pytest

from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
    TranscriptionJob,
)


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


def test_job_moves_uploaded_queued_processing_completed() -> None:
    uploaded = sample_job()

    queued = uploaded.mark_queued()
    processing = queued.mark_processing()
    completed = processing.mark_completed()

    assert queued.status is JobStatus.QUEUED
    assert processing.status is JobStatus.PROCESSING
    assert completed.status is JobStatus.COMPLETED
    assert completed.failure_code is None


def test_processing_failure_can_be_requeued_for_retry() -> None:
    processing = sample_job().mark_queued().mark_processing()

    failed = processing.mark_failed(JobFailureCode.PROCESSING_ERROR)
    retried = failed.mark_queued()

    assert failed.status is JobStatus.FAILED
    assert failed.failure_code is JobFailureCode.PROCESSING_ERROR
    assert retried.status is JobStatus.QUEUED
    assert retried.failure_code is None


@pytest.mark.parametrize(
    ("job", "operation"),
    [
        (sample_job(), "mark_processing"),
        (sample_job(), "mark_completed"),
        (sample_job().mark_queued(), "mark_completed"),
    ],
)
def test_invalid_job_transition_is_rejected(
    job: TranscriptionJob,
    operation: str,
) -> None:
    with pytest.raises(ValueError, match="invalid transcription job transition"):
        getattr(job, operation)()


def test_completed_job_cannot_be_failed_or_requeued() -> None:
    completed = sample_job().mark_queued().mark_processing().mark_completed()

    with pytest.raises(ValueError, match="invalid transcription job transition"):
        completed.mark_failed(JobFailureCode.PROCESSING_ERROR)

    with pytest.raises(ValueError, match="invalid transcription job transition"):
        completed.mark_queued()
