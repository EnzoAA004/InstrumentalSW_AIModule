from uuid import UUID

from pydantic import BaseModel, ConfigDict

from saxo_ai.domain.models import InputMode, JobStatus, SaxophoneType


class HealthResponse(BaseModel):
    status: str


class TranscriptionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: JobStatus
    filename: str
    size_bytes: int
    audio_sha256: str
    saxophone_type: SaxophoneType
    input_mode: InputMode
