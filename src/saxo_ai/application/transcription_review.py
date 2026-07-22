from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from saxo_ai.application.errors import (
    TranscriptionJobNotFoundError,
    TranscriptionResultNotReadyError,
    TranscriptionReviewInstrumentMismatchError,
)
from saxo_ai.application.ports import (
    TranscriptionJobRepository,
    TranscriptionReviewRegistrationRepository,
    TranscriptionReviewRepository,
)
from saxo_ai.application.transcription_revisions import Clock, build_revision_zero
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.note_confidence import CONFIDENCE_INTERPRETATION
from saxo_ai.domain.note_events import NOTE_EVENT_SCHEMA_VERSION
from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult

TRANSCRIPTION_REVIEW_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class TranscriptionReviewEvent:
    index: int
    pitch_concert_midi: int
    written_pitch_midi: int
    onset_seconds: float
    offset_seconds: float
    velocity: int
    confidence: float
    is_low_confidence: bool


@dataclass(frozen=True, slots=True)
class TranscriptionReviewSummary:
    event_count: int
    low_confidence_count: int


@dataclass(frozen=True, slots=True)
class TranscriptionReviewSnapshot:
    job_id: UUID
    schema_version: str
    note_event_schema_version: str
    low_confidence_policy_version: str
    written_pitch_policy_version: str
    saxophone_type: SaxophoneType
    low_confidence_threshold: float
    confidence_interpretation: str
    confidence_method: str
    summary: TranscriptionReviewSummary
    events: tuple[TranscriptionReviewEvent, ...]


class RegisterTranscriptionReview:
    def __init__(
        self,
        jobs: TranscriptionJobRepository,
        registrations: TranscriptionReviewRegistrationRepository,
        clock: Clock | None = None,
    ) -> None:
        self._jobs = jobs
        self._registrations = registrations
        self._clock = clock

    def execute(
        self,
        job_id: UUID,
        result: WrittenPitchTranscriptionResult,
    ) -> WrittenPitchTranscriptionResult:
        job = self._jobs.get(job_id)
        if job is None:
            raise TranscriptionJobNotFoundError
        if result.saxophone_type is not job.saxophone_type:
            raise TranscriptionReviewInstrumentMismatchError
        created_at = self._clock() if self._clock is not None else datetime.now(UTC)
        revision_zero = build_revision_zero(job_id, result, created_at)
        return self._registrations.initialize(job_id, result, revision_zero)


class GetTranscriptionReview:
    def __init__(
        self,
        jobs: TranscriptionJobRepository,
        reviews: TranscriptionReviewRepository,
    ) -> None:
        self._jobs = jobs
        self._reviews = reviews

    def execute(self, job_id: UUID) -> TranscriptionReviewSnapshot:
        job = self._jobs.get(job_id)
        if job is None:
            raise TranscriptionJobNotFoundError
        result = self._reviews.get(job_id)
        if result is None:
            raise TranscriptionResultNotReadyError
        if result.saxophone_type is not job.saxophone_type:
            raise TranscriptionReviewInstrumentMismatchError
        return build_transcription_review_snapshot(job_id, result)


def build_transcription_review_snapshot(
    job_id: UUID,
    result: WrittenPitchTranscriptionResult,
) -> TranscriptionReviewSnapshot:
    events = tuple(
        TranscriptionReviewEvent(
            index=index,
            pitch_concert_midi=written.source.event.pitch_concert_midi,
            written_pitch_midi=written.written_pitch_midi,
            onset_seconds=written.source.event.onset_seconds,
            offset_seconds=written.source.event.offset_seconds,
            velocity=written.source.event.velocity,
            confidence=written.source.event.confidence,
            is_low_confidence=written.source.is_low_confidence,
        )
        for index, written in enumerate(result.events)
    )
    low_confidence_count = sum(event.is_low_confidence for event in events)
    settings = result.original.report.settings
    transcription_settings = result.original.original.original.settings
    return TranscriptionReviewSnapshot(
        job_id=job_id,
        schema_version=TRANSCRIPTION_REVIEW_SCHEMA_VERSION,
        note_event_schema_version=NOTE_EVENT_SCHEMA_VERSION,
        low_confidence_policy_version=settings.policy_version,
        written_pitch_policy_version=result.policy_version,
        saxophone_type=result.saxophone_type,
        low_confidence_threshold=settings.low_confidence_threshold,
        confidence_interpretation=CONFIDENCE_INTERPRETATION,
        confidence_method=transcription_settings.confidence_method,
        summary=TranscriptionReviewSummary(
            event_count=len(events),
            low_confidence_count=low_confidence_count,
        ),
        events=events,
    )
