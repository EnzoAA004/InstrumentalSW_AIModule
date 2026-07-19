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
    FAILED = "FAILED"


class JobFailureCode(StrEnum):
    AUDIO_CONTENT_INVALID = "AUDIO_CONTENT_INVALID"


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

    def mark_failed(self, failure_code: JobFailureCode) -> TranscriptionJob:
        return replace(self, status=JobStatus.FAILED, failure_code=failure_code)
