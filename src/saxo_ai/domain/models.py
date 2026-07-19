from dataclasses import dataclass
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
