from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID


class SaxophoneType(StrEnum):
    SOPRANO = "soprano"
    ALTO = "alto"
    TENOR = "tenor"
    BARITONE = "baritone"


class InputMode(StrEnum):
    SOLO = "solo"
    MIXTURE = "mixture"


class JobStatus(StrEnum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobFailureCode(StrEnum):
    AUDIO_CONTENT_INVALID = "AUDIO_CONTENT_INVALID"
    AUDIO_DURATION_LIMIT_EXCEEDED = "AUDIO_DURATION_LIMIT_EXCEEDED"
    SOURCE_AUDIO_MISSING = "SOURCE_AUDIO_MISSING"
    PROCESSING_FAILED = "PROCESSING_FAILED"


@dataclass(frozen=True, slots=True)
class AudioContentMetadata:
    size_bytes: int
    audio_sha256: str


@dataclass(frozen=True, slots=True)
class TranscriptionJob:
    job_id: UUID
    status: JobStatus
    filename: str
    size_bytes: int
    audio_sha256: str
    saxophone_type: SaxophoneType
    input_mode: InputMode
    failure_code: JobFailureCode | None = None

    def __post_init__(self) -> None:
        if self.status is JobStatus.FAILED and self.failure_code is None:
            raise ValueError("a FAILED transcription job requires a failure_code")
        if self.status is not JobStatus.FAILED and self.failure_code is not None:
            raise ValueError("a non-failed transcription job cannot have a failure_code")

    def mark_queued(self) -> TranscriptionJob:
        return self._transition(
            JobStatus.QUEUED,
            allowed_from=(JobStatus.UPLOADED, JobStatus.PROCESSING),
        )

    def mark_processing(self) -> TranscriptionJob:
        if self.status is JobStatus.PROCESSING:
            return self
        return self._transition(JobStatus.PROCESSING, allowed_from=(JobStatus.QUEUED,))

    def mark_completed(self) -> TranscriptionJob:
        return self._transition(JobStatus.COMPLETED, allowed_from=(JobStatus.PROCESSING,))

    def mark_failed(self, failure_code: JobFailureCode) -> TranscriptionJob:
        if self.status is JobStatus.COMPLETED:
            raise ValueError("cannot transition a COMPLETED transcription job to FAILED")
        return replace(self, status=JobStatus.FAILED, failure_code=failure_code)

    def _transition(
        self,
        target: JobStatus,
        *,
        allowed_from: tuple[JobStatus, ...],
    ) -> TranscriptionJob:
        if self.status not in allowed_from:
            raise ValueError(f"cannot transition transcription job from {self.status} to {target}")
        return replace(self, status=target, failure_code=None)
