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
    PROCESSING_ERROR = "PROCESSING_ERROR"


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
        self._require_transition(
            target=JobStatus.QUEUED,
            allowed_sources={JobStatus.UPLOADED, JobStatus.FAILED},
        )
        return replace(self, status=JobStatus.QUEUED, failure_code=None)

    def mark_processing(self) -> TranscriptionJob:
        self._require_transition(
            target=JobStatus.PROCESSING,
            allowed_sources={JobStatus.QUEUED},
        )
        return replace(self, status=JobStatus.PROCESSING, failure_code=None)

    def mark_completed(self) -> TranscriptionJob:
        self._require_transition(
            target=JobStatus.COMPLETED,
            allowed_sources={JobStatus.PROCESSING},
        )
        return replace(self, status=JobStatus.COMPLETED, failure_code=None)

    def mark_failed(self, failure_code: JobFailureCode) -> TranscriptionJob:
        self._require_transition(
            target=JobStatus.FAILED,
            allowed_sources={
                JobStatus.UPLOADED,
                JobStatus.QUEUED,
                JobStatus.PROCESSING,
                JobStatus.FAILED,
            },
        )
        return replace(self, status=JobStatus.FAILED, failure_code=failure_code)

    def _require_transition(
        self,
        *,
        target: JobStatus,
        allowed_sources: set[JobStatus],
    ) -> None:
        if self.status not in allowed_sources:
            raise ValueError(
                f"invalid transcription job transition: {self.status.value} -> {target.value}"
            )
