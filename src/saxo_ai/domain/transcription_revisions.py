from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from saxo_ai.domain.models import SaxophoneType

TRANSCRIPTION_REVISION_SCHEMA_VERSION = "1.0"
DEFAULT_HUMAN_VELOCITY = 64
REQUESTED_DERIVED_ARTIFACTS = ("midi", "musicxml", "svg")


class EventOrigin(StrEnum):
    MODEL = "model"
    HUMAN = "human"


class DerivedArtifactsStatus(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    REGENERATION_REQUESTED = "REGENERATION_REQUESTED"


class RegenerationRequestStatus(StrEnum):
    REQUESTED = "REQUESTED"


class InvalidTranscriptionRevisionError(ValueError):
    """Raised when an immutable transcription revision violates its contract."""


class InvalidRevisionEventError(InvalidTranscriptionRevisionError):
    """Raised when a revision event violates pitch, timing, identity, or provenance rules."""


def _require_midi_integer(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 127:
        raise InvalidRevisionEventError(f"{field_name} must be an integer between 0 and 127")
    return value


def _require_finite_time(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidRevisionEventError(f"{field_name} must be a finite number")
    converted = float(value)
    if not math.isfinite(converted):
        raise InvalidRevisionEventError(f"{field_name} must be a finite number")
    return converted


@dataclass(frozen=True, slots=True)
class TranscriptionRevisionEvent:
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

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id:
            raise InvalidRevisionEventError("event_id must be a non-empty string")
        if not isinstance(self.origin, EventOrigin):
            raise InvalidRevisionEventError("origin must be model or human")
        _require_midi_integer("pitch_concert_midi", self.pitch_concert_midi)
        _require_midi_integer("written_pitch_midi", self.written_pitch_midi)
        onset = _require_finite_time("onset_seconds", self.onset_seconds)
        offset = _require_finite_time("offset_seconds", self.offset_seconds)
        if onset < 0:
            raise InvalidRevisionEventError("onset_seconds must be non-negative")
        if offset <= onset:
            raise InvalidRevisionEventError("offset_seconds must be greater than onset_seconds")
        velocity = _require_midi_integer("velocity", self.velocity)
        object.__setattr__(self, "onset_seconds", onset)
        object.__setattr__(self, "offset_seconds", offset)
        object.__setattr__(self, "velocity", velocity)

        if self.origin is EventOrigin.MODEL:
            if isinstance(self.source_index, bool) or not isinstance(self.source_index, int):
                raise InvalidRevisionEventError("model events require an integer source_index")
            if self.source_index < 0 or self.event_id != f"source-{self.source_index}":
                raise InvalidRevisionEventError("model event identity must match source_index")
            if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
                raise InvalidRevisionEventError("model events require confidence")
            confidence = float(self.confidence)
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise InvalidRevisionEventError("confidence must be finite between 0 and 1")
            if not isinstance(self.is_low_confidence, bool):
                raise InvalidRevisionEventError("model events require is_low_confidence")
            object.__setattr__(self, "confidence", confidence)
        else:
            if self.source_index is not None:
                raise InvalidRevisionEventError("human events must not have source_index")
            if self.confidence is not None or self.is_low_confidence is not None:
                raise InvalidRevisionEventError("human events must not claim model confidence")
            if not self.event_id.startswith("human-"):
                raise InvalidRevisionEventError("human event_id must use the human-UUID form")
            try:
                UUID(self.event_id.removeprefix("human-"))
            except ValueError as error:
                raise InvalidRevisionEventError("human event_id must contain a UUID") from error


@dataclass(frozen=True, slots=True)
class TranscriptionRevisionSummary:
    event_count: int
    model_event_count: int
    human_event_count: int

    def __post_init__(self) -> None:
        values = (self.event_count, self.model_event_count, self.human_event_count)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            raise InvalidTranscriptionRevisionError("revision summary counts must be non-negative integers")
        if self.event_count != self.model_event_count + self.human_event_count:
            raise InvalidTranscriptionRevisionError("revision summary counts must be consistent")


@dataclass(frozen=True, slots=True)
class TranscriptionRevision:
    job_id: UUID
    revision_number: int
    parent_revision_number: int | None
    created_at: datetime
    saxophone_type: SaxophoneType
    events: tuple[TranscriptionRevisionEvent, ...]
    derived_artifacts_status: DerivedArtifactsStatus
    summary: TranscriptionRevisionSummary = field(init=False)
    schema_version: str = TRANSCRIPTION_REVISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, UUID):
            raise InvalidTranscriptionRevisionError("job_id must be a UUID")
        if isinstance(self.revision_number, bool) or not isinstance(self.revision_number, int):
            raise InvalidTranscriptionRevisionError("revision_number must be an integer")
        if self.revision_number < 0:
            raise InvalidTranscriptionRevisionError("revision_number must be non-negative")
        expected_parent = None if self.revision_number == 0 else self.revision_number - 1
        if self.parent_revision_number != expected_parent:
            raise InvalidTranscriptionRevisionError("parent revision must be the prior revision")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise InvalidTranscriptionRevisionError("created_at must be timezone-aware")
        if not isinstance(self.saxophone_type, SaxophoneType):
            raise InvalidTranscriptionRevisionError("saxophone_type must be valid")
        if not isinstance(self.events, tuple) or not all(
            isinstance(event, TranscriptionRevisionEvent) for event in self.events
        ):
            raise InvalidTranscriptionRevisionError("events must be a tuple of revision events")
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise InvalidTranscriptionRevisionError("event_id values must be unique")
        if not isinstance(self.derived_artifacts_status, DerivedArtifactsStatus):
            raise InvalidTranscriptionRevisionError("derived_artifacts_status must be valid")
        if self.schema_version != TRANSCRIPTION_REVISION_SCHEMA_VERSION:
            raise InvalidTranscriptionRevisionError(
                f"schema_version must be {TRANSCRIPTION_REVISION_SCHEMA_VERSION}"
            )
        model_count = sum(event.origin is EventOrigin.MODEL for event in self.events)
        object.__setattr__(
            self,
            "summary",
            TranscriptionRevisionSummary(
                event_count=len(self.events),
                model_event_count=model_count,
                human_event_count=len(self.events) - model_count,
            ),
        )

    def with_derived_artifacts_status(
        self, status: DerivedArtifactsStatus
    ) -> TranscriptionRevision:
        return replace(self, derived_artifacts_status=status)


@dataclass(frozen=True, slots=True)
class TranscriptionRevisionHistoryEntry:
    revision_number: int
    parent_revision_number: int | None
    created_at: datetime
    event_count: int
    model_event_count: int
    human_event_count: int
    derived_artifacts_status: DerivedArtifactsStatus

    @classmethod
    def from_revision(cls, revision: TranscriptionRevision) -> TranscriptionRevisionHistoryEntry:
        return cls(
            revision_number=revision.revision_number,
            parent_revision_number=revision.parent_revision_number,
            created_at=revision.created_at,
            event_count=revision.summary.event_count,
            model_event_count=revision.summary.model_event_count,
            human_event_count=revision.summary.human_event_count,
            derived_artifacts_status=revision.derived_artifacts_status,
        )


@dataclass(frozen=True, slots=True)
class TranscriptionRevisionHistory:
    job_id: UUID
    latest_revision_number: int
    revision_count: int
    revisions: tuple[TranscriptionRevisionHistoryEntry, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, UUID):
            raise InvalidTranscriptionRevisionError("job_id must be a UUID")
        if self.revision_count != len(self.revisions) or self.revision_count < 1:
            raise InvalidTranscriptionRevisionError("revision_count must match revisions")
        numbers = tuple(entry.revision_number for entry in self.revisions)
        if numbers != tuple(range(self.revision_count)):
            raise InvalidTranscriptionRevisionError("revision history must be sequential from zero")
        if self.latest_revision_number != self.revision_count - 1:
            raise InvalidTranscriptionRevisionError("latest revision must be the final entry")


@dataclass(frozen=True, slots=True)
class RegenerationRequest:
    request_id: UUID
    job_id: UUID
    revision_number: int
    status: RegenerationRequestStatus
    requested_artifacts: tuple[str, ...]
    requested_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, UUID) or not isinstance(self.job_id, UUID):
            raise InvalidTranscriptionRevisionError("request and job IDs must be UUID values")
        if isinstance(self.revision_number, bool) or not isinstance(self.revision_number, int):
            raise InvalidTranscriptionRevisionError("revision_number must be an integer")
        if self.revision_number < 0:
            raise InvalidTranscriptionRevisionError("revision_number must be non-negative")
        if self.status is not RegenerationRequestStatus.REQUESTED:
            raise InvalidTranscriptionRevisionError("regeneration status must be REQUESTED")
        if self.requested_artifacts != REQUESTED_DERIVED_ARTIFACTS:
            raise InvalidTranscriptionRevisionError("requested artifacts must be midi, musicxml, svg")
        if not isinstance(self.requested_at, datetime) or self.requested_at.tzinfo is None:
            raise InvalidTranscriptionRevisionError("requested_at must be timezone-aware")
