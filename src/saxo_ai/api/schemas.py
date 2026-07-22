from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from saxo_ai.domain.models import InputMode, JobStatus, SaxophoneType
from saxo_ai.domain.revision_artifacts import ArtifactType
from saxo_ai.domain.transcription_revisions import (
    DerivedArtifactsStatus,
    EventOrigin,
    RegenerationRequestStatus,
)


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


class TranscriptionRevisionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    origin: EventOrigin
    source_index: int | None
    pitch_concert_midi: int
    written_pitch_midi: int
    onset_seconds: float
    offset_seconds: float
    velocity: int
    confidence: float | None
    is_low_confidence: bool | None


class TranscriptionRevisionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_count: int
    model_event_count: int
    human_event_count: int


class TranscriptionRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    revision_number: int
    parent_revision_number: int | None
    created_at: datetime
    saxophone_type: SaxophoneType
    events: tuple[TranscriptionRevisionEventResponse, ...]
    summary: TranscriptionRevisionSummaryResponse
    derived_artifacts_status: DerivedArtifactsStatus
    schema_version: str


class TranscriptionRevisionHistoryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    revision_number: int
    parent_revision_number: int | None
    created_at: datetime
    event_count: int
    model_event_count: int
    human_event_count: int
    derived_artifacts_status: DerivedArtifactsStatus


class TranscriptionRevisionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    latest_revision_number: int
    revision_count: int
    revisions: tuple[TranscriptionRevisionHistoryEntryResponse, ...]


class RegenerationRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: UUID
    job_id: UUID
    revision_number: int
    status: RegenerationRequestStatus
    requested_artifacts: tuple[str, ...]


class RevisionArtifactDescriptorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: str
    artifact_type: ArtifactType
    filename: str
    media_type: str
    extension: str
    size_bytes: int
    sha256: str
    order: int


class RevisionArtifactListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    revision_number: int
    artifacts: tuple[RevisionArtifactDescriptorResponse, ...]
