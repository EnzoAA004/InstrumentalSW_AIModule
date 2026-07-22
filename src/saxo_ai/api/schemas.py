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


class TranscriptionReviewEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int
    pitch_concert_midi: int
    written_pitch_midi: int
    onset_seconds: float
    offset_seconds: float
    velocity: int
    confidence: float
    is_low_confidence: bool


class TranscriptionReviewSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_count: int
    low_confidence_count: int


class TranscriptionReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    schema_version: str
    note_event_schema_version: str
    low_confidence_policy_version: str
    written_pitch_policy_version: str
    saxophone_type: SaxophoneType
    low_confidence_threshold: float
    confidence_interpretation: str
    confidence_method: str
    summary: TranscriptionReviewSummaryResponse
    events: tuple[TranscriptionReviewEventResponse, ...]
