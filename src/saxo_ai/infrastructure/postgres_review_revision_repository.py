from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, RowMapping, func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import IntegrityError

from saxo_ai.application.errors import (
    RevisionConflictError,
    TranscriptionReviewInstrumentMismatchError,
)
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.note_confidence import (
    ConfidenceAnnotatedNoteEvent,
    ConfidenceAnnotatedTranscriptionResult,
    LowConfidenceReport,
    LowConfidenceSettings,
)
from saxo_ai.domain.note_event_postprocessing import (
    NoteEventPostProcessingReport,
    NoteEventPostProcessingSettings,
    PostProcessedTranscriptionResult,
)
from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.transcription_revisions import (
    REQUESTED_DERIVED_ARTIFACTS,
    DerivedArtifactsStatus,
    EventOrigin,
    RegenerationRequest,
    RegenerationRequestStatus,
    TranscriptionRevision,
    TranscriptionRevisionEvent,
)
from saxo_ai.domain.written_pitch import (
    WrittenPitchNoteEvent,
    WrittenPitchTranscriptionResult,
)
from saxo_ai.infrastructure.postgres_schema import (
    regeneration_requests,
    transcription_review_events,
    transcription_reviews,
    transcription_revision_events,
    transcription_revisions,
)

_REQUESTED_ARTIFACTS_STORAGE = ",".join(REQUESTED_DERIVED_ARTIFACTS)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class PostgresTranscriptionReviewRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, job_id: UUID, result: WrittenPitchTranscriptionResult) -> None:
        with self._engine.begin() as connection:
            _insert_review(connection, job_id, result)

    def get(self, job_id: UUID) -> WrittenPitchTranscriptionResult | None:
        with self._engine.connect() as connection:
            return _load_review(connection, job_id)


class PostgresTranscriptionReviewRegistrationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def initialize(
        self,
        job_id: UUID,
        result: WrittenPitchTranscriptionResult,
        revision_zero: TranscriptionRevision,
    ) -> WrittenPitchTranscriptionResult:
        if (
            revision_zero.job_id != job_id
            or revision_zero.revision_number != 0
            or revision_zero.parent_revision_number is not None
        ):
            raise ValueError("review registration requires matching revision zero")

        with self._engine.begin() as connection:
            existing_review = _load_review(connection, job_id)
            existing_revision = _load_revision(connection, job_id, 0)
            if existing_review is not None or existing_revision is not None:
                if existing_review is None or existing_revision is None:
                    raise TranscriptionReviewInstrumentMismatchError
                if not _same_review_source(existing_review, result):
                    raise TranscriptionReviewInstrumentMismatchError
                if existing_revision != revision_zero:
                    raise TranscriptionReviewInstrumentMismatchError
                return existing_review

            _insert_review(connection, job_id, result)
            _insert_revision(connection, revision_zero)
        return result


class PostgresTranscriptionRevisionRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def initialize(self, job_id: UUID, revision: TranscriptionRevision) -> TranscriptionRevision:
        if revision.job_id != job_id or revision.revision_number != 0:
            raise ValueError("revision initialization requires matching revision zero")
        with self._engine.begin() as connection:
            existing = _load_revision(connection, job_id, 0)
            if existing is not None:
                return existing
            _insert_revision(connection, revision)
        return revision

    def latest(self, job_id: UUID) -> TranscriptionRevision | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(func.max(transcription_revisions.c.revision_number)).where(
                    transcription_revisions.c.job_id == job_id
                )
            ).first()
            if row is None or row[0] is None:
                return None
            return _load_revision(connection, job_id, int(row[0]))

    def get(self, job_id: UUID, revision_number: int) -> TranscriptionRevision | None:
        if isinstance(revision_number, bool) or not isinstance(revision_number, int):
            return None
        with self._engine.connect() as connection:
            return _load_revision(connection, job_id, revision_number)

    def list(self, job_id: UUID) -> tuple[TranscriptionRevision, ...]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                select(transcription_revisions.c.revision_number)
                .where(transcription_revisions.c.job_id == job_id)
                .order_by(transcription_revisions.c.revision_number)
            ).all()
            return tuple(_load_revision_required(connection, job_id, int(row[0])) for row in rows)

    def append(
        self,
        job_id: UUID,
        expected_latest_revision: int,
        revision: TranscriptionRevision,
    ) -> None:
        if revision.job_id != job_id:
            raise ValueError("revision job_id must match repository key")
        if revision.revision_number != expected_latest_revision + 1:
            raise ValueError("revision number must follow expected latest revision")

        with self._engine.begin() as connection:
            latest_row = connection.execute(
                select(transcription_revisions.c.revision_number)
                .where(transcription_revisions.c.job_id == job_id)
                .order_by(transcription_revisions.c.revision_number.desc())
                .with_for_update()
                .limit(1)
            ).first()
            if latest_row is None or int(latest_row[0]) != expected_latest_revision:
                raise RevisionConflictError
            try:
                _insert_revision(connection, revision)
            except IntegrityError as error:
                raise RevisionConflictError from error


class PostgresRegenerationRequestRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, job_id: UUID, revision_number: int) -> RegenerationRequest | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    regeneration_requests.select()
                    .where(regeneration_requests.c.job_id == job_id)
                    .where(regeneration_requests.c.revision_number == revision_number)
                )
                .mappings()
                .first()
            )
        return None if row is None else _request_from_row(row)

    def save(self, request: RegenerationRequest) -> RegenerationRequest:
        statement = postgres_insert(regeneration_requests).values(
            request_id=request.request_id,
            job_id=request.job_id,
            revision_number=request.revision_number,
            status=request.status.value,
            requested_artifacts=_REQUESTED_ARTIFACTS_STORAGE,
            requested_at=request.requested_at,
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=[
                regeneration_requests.c.job_id,
                regeneration_requests.c.revision_number,
            ]
        )
        with self._engine.begin() as connection:
            connection.execute(statement)
            row = (
                connection.execute(
                    regeneration_requests.select()
                    .where(regeneration_requests.c.job_id == request.job_id)
                    .where(regeneration_requests.c.revision_number == request.revision_number)
                )
                .mappings()
                .one()
            )
        return _request_from_row(row)


def _insert_review(
    connection: Any,
    job_id: UUID,
    result: WrittenPitchTranscriptionResult,
) -> None:
    confidence = result.original
    processed = confidence.original
    raw = processed.original
    row = {
        "job_id": job_id,
        "saxophone_type": result.saxophone_type.value,
        "low_confidence_threshold": confidence.report.settings.low_confidence_threshold,
        "confidence_method": raw.settings.confidence_method,
        "engine_name": raw.model.engine_name,
        "engine_version": raw.model.engine_version,
        "engine_source_revision": raw.model.engine_source_revision,
        "model_id": raw.model.model_id,
        "model_revision": raw.model.model_revision,
        "checkpoint_filename": raw.model.checkpoint_filename,
        "checkpoint_sha256": raw.model.checkpoint_sha256,
        "sample_rate_hz": raw.settings.sample_rate_hz,
        "device": raw.settings.device,
        "onset_threshold": raw.settings.onset_threshold,
        "offset_threshold": raw.settings.offset_threshold,
        "frame_threshold": raw.settings.frame_threshold,
    }
    connection.execute(transcription_reviews.insert().values(**row))
    if result.events:
        connection.execute(
            transcription_review_events.insert(),
            [
                {
                    "job_id": job_id,
                    "event_index": index,
                    "pitch_concert_midi": event.source.event.pitch_concert_midi,
                    "written_pitch_midi": event.written_pitch_midi,
                    "onset_seconds": event.source.event.onset_seconds,
                    "offset_seconds": event.source.event.offset_seconds,
                    "velocity": event.source.event.velocity,
                    "confidence": event.source.event.confidence,
                    "is_low_confidence": event.source.is_low_confidence,
                }
                for index, event in enumerate(result.events)
            ],
        )


def _load_review(connection: Any, job_id: UUID) -> WrittenPitchTranscriptionResult | None:
    review = (
        connection.execute(
            transcription_reviews.select().where(transcription_reviews.c.job_id == job_id)
        )
        .mappings()
        .first()
    )
    if review is None:
        return None
    event_rows = (
        connection.execute(
            transcription_review_events.select()
            .where(transcription_review_events.c.job_id == job_id)
            .order_by(transcription_review_events.c.event_index)
        )
        .mappings()
        .all()
    )
    return _review_from_rows(review, event_rows)


def _review_from_rows(
    review: RowMapping,
    event_rows: list[RowMapping],
) -> WrittenPitchTranscriptionResult:
    notes = tuple(
        NoteEvent(
            pitch_concert_midi=row["pitch_concert_midi"],
            onset_seconds=row["onset_seconds"],
            offset_seconds=row["offset_seconds"],
            velocity=row["velocity"],
            confidence=row["confidence"],
        )
        for row in event_rows
    )
    batch = NoteEventBatch(notes)
    raw = TranscriptionResult(
        notes=batch,
        model=TranscriptionModelIdentity(
            engine_name=review["engine_name"],
            engine_version=review["engine_version"],
            engine_source_revision=review["engine_source_revision"],
            model_id=review["model_id"],
            model_revision=review["model_revision"],
            checkpoint_filename=review["checkpoint_filename"],
            checkpoint_sha256=review["checkpoint_sha256"],
        ),
        settings=TranscriptionSettings(
            sample_rate_hz=review["sample_rate_hz"],
            device=review["device"],
            onset_threshold=review["onset_threshold"],
            offset_threshold=review["offset_threshold"],
            frame_threshold=review["frame_threshold"],
            confidence_method=review["confidence_method"],
        ),
    )
    processed = PostProcessedTranscriptionResult(
        original=raw,
        notes=batch,
        report=NoteEventPostProcessingReport(
            settings=NoteEventPostProcessingSettings(),
            input_event_count=len(notes),
            output_event_count=len(notes),
            short_duration_removed_count=0,
            duplicate_removed_count=0,
            duplicate_group_count=0,
        ),
    )
    annotations = tuple(
        ConfidenceAnnotatedNoteEvent(
            event=note,
            is_low_confidence=event_rows[index]["is_low_confidence"],
        )
        for index, note in enumerate(notes)
    )
    low_count = sum(annotation.is_low_confidence for annotation in annotations)
    confidence = ConfidenceAnnotatedTranscriptionResult(
        original=processed,
        annotated_events=annotations,
        report=LowConfidenceReport(
            settings=LowConfidenceSettings(
                low_confidence_threshold=review["low_confidence_threshold"]
            ),
            input_event_count=len(notes),
            low_confidence_count=low_count,
            regular_confidence_count=len(notes) - low_count,
        ),
    )
    return WrittenPitchTranscriptionResult(
        original=confidence,
        saxophone_type=SaxophoneType(review["saxophone_type"]),
        events=tuple(
            WrittenPitchNoteEvent(
                source=annotations[index],
                written_pitch_midi=row["written_pitch_midi"],
            )
            for index, row in enumerate(event_rows)
        ),
    )


def _same_review_source(
    existing: WrittenPitchTranscriptionResult,
    candidate: WrittenPitchTranscriptionResult,
) -> bool:
    existing_confidence = existing.original
    candidate_confidence = candidate.original
    existing_raw = existing_confidence.original.original
    candidate_raw = candidate_confidence.original.original
    return (
        existing.saxophone_type == candidate.saxophone_type
        and existing_confidence.report.settings == candidate_confidence.report.settings
        and existing_raw.model == candidate_raw.model
        and existing_raw.settings == candidate_raw.settings
        and _same_review_events(existing, candidate)
    )


def _same_review_events(
    existing: WrittenPitchTranscriptionResult,
    candidate: WrittenPitchTranscriptionResult,
) -> bool:
    if len(existing.events) != len(candidate.events):
        return False
    return all(
        existing_event.written_pitch_midi == candidate_event.written_pitch_midi
        and existing_event.source.is_low_confidence == candidate_event.source.is_low_confidence
        and existing_event.source.event == candidate_event.source.event
        for existing_event, candidate_event in zip(existing.events, candidate.events, strict=True)
    )


def _insert_revision(connection: Any, revision: TranscriptionRevision) -> None:
    connection.execute(
        transcription_revisions.insert().values(
            job_id=revision.job_id,
            revision_number=revision.revision_number,
            parent_revision_number=revision.parent_revision_number,
            created_at=revision.created_at,
            saxophone_type=revision.saxophone_type.value,
            derived_artifacts_status=revision.derived_artifacts_status.value,
        )
    )
    if revision.events:
        connection.execute(
            transcription_revision_events.insert(),
            [
                {
                    "job_id": revision.job_id,
                    "revision_number": revision.revision_number,
                    "event_id": event.event_id,
                    "order_index": index,
                    "origin": event.origin.value,
                    "source_index": event.source_index,
                    "pitch_concert_midi": event.pitch_concert_midi,
                    "written_pitch_midi": event.written_pitch_midi,
                    "onset_seconds": event.onset_seconds,
                    "offset_seconds": event.offset_seconds,
                    "velocity": event.velocity,
                    "confidence": event.confidence,
                    "is_low_confidence": event.is_low_confidence,
                }
                for index, event in enumerate(revision.events)
            ],
        )


def _load_revision(
    connection: Any,
    job_id: UUID,
    revision_number: int,
) -> TranscriptionRevision | None:
    revision = (
        connection.execute(
            transcription_revisions.select()
            .where(transcription_revisions.c.job_id == job_id)
            .where(transcription_revisions.c.revision_number == revision_number)
        )
        .mappings()
        .first()
    )
    if revision is None:
        return None
    event_rows = (
        connection.execute(
            transcription_revision_events.select()
            .where(transcription_revision_events.c.job_id == job_id)
            .where(transcription_revision_events.c.revision_number == revision_number)
            .order_by(transcription_revision_events.c.order_index)
        )
        .mappings()
        .all()
    )
    return TranscriptionRevision(
        job_id=job_id,
        revision_number=revision["revision_number"],
        parent_revision_number=revision["parent_revision_number"],
        created_at=_ensure_utc(revision["created_at"]),
        saxophone_type=SaxophoneType(revision["saxophone_type"]),
        events=tuple(_revision_event_from_row(row) for row in event_rows),
        derived_artifacts_status=DerivedArtifactsStatus(revision["derived_artifacts_status"]),
    )


def _load_revision_required(
    connection: Any,
    job_id: UUID,
    revision_number: int,
) -> TranscriptionRevision:
    revision = _load_revision(connection, job_id, revision_number)
    if revision is None:
        raise RuntimeError("revision disappeared during read")
    return revision


def _revision_event_from_row(row: RowMapping) -> TranscriptionRevisionEvent:
    return TranscriptionRevisionEvent(
        event_id=row["event_id"],
        origin=EventOrigin(row["origin"]),
        source_index=row["source_index"],
        pitch_concert_midi=row["pitch_concert_midi"],
        written_pitch_midi=row["written_pitch_midi"],
        onset_seconds=row["onset_seconds"],
        offset_seconds=row["offset_seconds"],
        velocity=row["velocity"],
        confidence=row["confidence"],
        is_low_confidence=row["is_low_confidence"],
    )


def _request_from_row(row: RowMapping) -> RegenerationRequest:
    requested_artifacts = tuple(str(row["requested_artifacts"]).split(","))
    return RegenerationRequest(
        request_id=row["request_id"],
        job_id=row["job_id"],
        revision_number=row["revision_number"],
        status=RegenerationRequestStatus(row["status"]),
        requested_artifacts=requested_artifacts,
        requested_at=_ensure_utc(row["requested_at"]),
    )
