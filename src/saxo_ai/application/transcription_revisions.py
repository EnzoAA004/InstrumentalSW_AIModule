from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from saxo_ai.application.errors import (
    InvalidRevisionEventError,
    InvalidRevisionOperationError,
    RevisionConflictError,
    RevisionNotFoundError,
)
from saxo_ai.application.ports import (
    RegenerationRequestRepository,
    TranscriptionRevisionRepository,
)
from saxo_ai.domain.transcription_revisions import (
    DEFAULT_HUMAN_VELOCITY,
    REQUESTED_DERIVED_ARTIFACTS,
    DerivedArtifactsStatus,
    EventOrigin,
    InvalidRevisionEventError as DomainInvalidRevisionEventError,
    RegenerationRequest,
    RegenerationRequestStatus,
    TranscriptionRevision,
    TranscriptionRevisionEvent,
    TranscriptionRevisionHistory,
    TranscriptionRevisionHistoryEntry,
)
from saxo_ai.domain.transposition import written_pitch_offset_for
from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult

Clock = Callable[[], datetime]
UuidFactory = Callable[[], UUID]


@dataclass(frozen=True, slots=True)
class UpdateRevisionEvent:
    event_id: str
    written_pitch_midi: int
    onset_seconds: float
    offset_seconds: float


@dataclass(frozen=True, slots=True)
class AddRevisionEvent:
    written_pitch_midi: int
    onset_seconds: float
    offset_seconds: float
    velocity: int = DEFAULT_HUMAN_VELOCITY


@dataclass(frozen=True, slots=True)
class DeleteRevisionEvent:
    event_id: str


RevisionOperation = UpdateRevisionEvent | AddRevisionEvent | DeleteRevisionEvent


def build_revision_zero(
    job_id: UUID,
    result: WrittenPitchTranscriptionResult,
    created_at: datetime,
) -> TranscriptionRevision:
    events = tuple(
        TranscriptionRevisionEvent(
            event_id=f"source-{index}",
            origin=EventOrigin.MODEL,
            source_index=index,
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
    return TranscriptionRevision(
        job_id=job_id,
        revision_number=0,
        parent_revision_number=None,
        created_at=created_at,
        saxophone_type=result.saxophone_type,
        events=events,
        derived_artifacts_status=DerivedArtifactsStatus.CURRENT,
    )


class CreateTranscriptionRevision:
    def __init__(
        self,
        revisions: TranscriptionRevisionRepository,
        clock: Clock,
        uuid_factory: UuidFactory,
    ) -> None:
        self._revisions = revisions
        self._clock = clock
        self._uuid_factory = uuid_factory

    def execute(
        self,
        job_id: UUID,
        *,
        base_revision_number: int,
        operations: tuple[object, ...],
    ) -> TranscriptionRevision:
        latest = self._revisions.latest(job_id)
        if latest is None:
            raise RevisionNotFoundError
        if (
            isinstance(base_revision_number, bool)
            or not isinstance(base_revision_number, int)
            or base_revision_number != latest.revision_number
        ):
            raise RevisionConflictError
        if not isinstance(operations, tuple) or not operations:
            raise InvalidRevisionOperationError("at least one operation is required")

        working = list(latest.events)
        touched: set[str] = set()
        all_historical_ids = {
            event.event_id
            for revision in self._revisions.list(job_id)
            for event in revision.events
        }
        for operation in operations:
            if isinstance(operation, UpdateRevisionEvent):
                self._reject_repeated_target(operation.event_id, touched)
                position = self._find_event(working, operation.event_id)
                current = working[position]
                working[position] = self._updated_event(current, operation, latest)
                touched.add(operation.event_id)
            elif isinstance(operation, DeleteRevisionEvent):
                self._reject_repeated_target(operation.event_id, touched)
                position = self._find_event(working, operation.event_id)
                working.pop(position)
                touched.add(operation.event_id)
            elif isinstance(operation, AddRevisionEvent):
                event_id = f"human-{self._uuid_factory()}"
                if event_id in all_historical_ids or any(
                    event.event_id == event_id for event in working
                ):
                    raise InvalidRevisionOperationError("event_id values must never be reused")
                working.append(self._human_event(event_id, operation, latest))
                all_historical_ids.add(event_id)
            else:
                raise InvalidRevisionOperationError("unsupported revision operation")

        revision = TranscriptionRevision(
            job_id=job_id,
            revision_number=latest.revision_number + 1,
            parent_revision_number=latest.revision_number,
            created_at=self._clock(),
            saxophone_type=latest.saxophone_type,
            events=tuple(working),
            derived_artifacts_status=DerivedArtifactsStatus.STALE,
        )
        self._revisions.append(job_id, latest.revision_number, revision)
        return revision

    @staticmethod
    def _reject_repeated_target(event_id: str, touched: set[str]) -> None:
        if not isinstance(event_id, str) or not event_id or event_id in touched:
            raise InvalidRevisionOperationError(
                "an event cannot be updated or deleted more than once"
            )

    @staticmethod
    def _find_event(events: list[TranscriptionRevisionEvent], event_id: str) -> int:
        for index, event in enumerate(events):
            if event.event_id == event_id:
                return index
        raise InvalidRevisionOperationError("revision operation references an unknown event_id")

    @staticmethod
    def _derive_concert_pitch(written_pitch_midi: object, revision: TranscriptionRevision) -> int:
        if (
            isinstance(written_pitch_midi, bool)
            or not isinstance(written_pitch_midi, int)
            or not 0 <= written_pitch_midi <= 127
        ):
            raise InvalidRevisionEventError(
                "written_pitch_midi must be an integer between 0 and 127"
            )
        concert = written_pitch_midi - written_pitch_offset_for(revision.saxophone_type)
        if not 0 <= concert <= 127:
            raise InvalidRevisionEventError(
                "derived pitch_concert_midi must be between 0 and 127"
            )
        return concert

    def _updated_event(
        self,
        current: TranscriptionRevisionEvent,
        operation: UpdateRevisionEvent,
        revision: TranscriptionRevision,
    ) -> TranscriptionRevisionEvent:
        try:
            return replace(
                current,
                written_pitch_midi=operation.written_pitch_midi,
                pitch_concert_midi=self._derive_concert_pitch(
                    operation.written_pitch_midi, revision
                ),
                onset_seconds=operation.onset_seconds,
                offset_seconds=operation.offset_seconds,
            )
        except DomainInvalidRevisionEventError as error:
            raise InvalidRevisionEventError(str(error)) from error

    def _human_event(
        self,
        event_id: str,
        operation: AddRevisionEvent,
        revision: TranscriptionRevision,
    ) -> TranscriptionRevisionEvent:
        try:
            return TranscriptionRevisionEvent(
                event_id=event_id,
                origin=EventOrigin.HUMAN,
                source_index=None,
                pitch_concert_midi=self._derive_concert_pitch(
                    operation.written_pitch_midi, revision
                ),
                written_pitch_midi=operation.written_pitch_midi,
                onset_seconds=operation.onset_seconds,
                offset_seconds=operation.offset_seconds,
                velocity=operation.velocity,
                confidence=None,
                is_low_confidence=None,
            )
        except DomainInvalidRevisionEventError as error:
            raise InvalidRevisionEventError(str(error)) from error


class GetTranscriptionRevision:
    def __init__(
        self,
        revisions: TranscriptionRevisionRepository,
        requests: RegenerationRequestRepository | None = None,
    ) -> None:
        self._revisions = revisions
        self._requests = requests

    def execute(self, job_id: UUID, revision_number: int) -> TranscriptionRevision:
        revision = self._revisions.get(job_id, revision_number)
        if revision is None:
            raise RevisionNotFoundError
        return _with_request_status(revision, self._requests)


class GetTranscriptionRevisionHistory:
    def __init__(
        self,
        revisions: TranscriptionRevisionRepository,
        requests: RegenerationRequestRepository | None = None,
    ) -> None:
        self._revisions = revisions
        self._requests = requests

    def execute(self, job_id: UUID) -> TranscriptionRevisionHistory:
        revisions = self._revisions.list(job_id)
        if not revisions:
            raise RevisionNotFoundError
        projected = tuple(
            _with_request_status(revision, self._requests) for revision in revisions
        )
        return TranscriptionRevisionHistory(
            job_id=job_id,
            latest_revision_number=projected[-1].revision_number,
            revision_count=len(projected),
            revisions=tuple(
                TranscriptionRevisionHistoryEntry.from_revision(revision)
                for revision in projected
            ),
        )


class RequestArtifactRegeneration:
    def __init__(
        self,
        revisions: TranscriptionRevisionRepository,
        requests: RegenerationRequestRepository,
        clock: Clock,
        uuid_factory: UuidFactory,
    ) -> None:
        self._revisions = revisions
        self._requests = requests
        self._clock = clock
        self._uuid_factory = uuid_factory

    def execute(self, job_id: UUID, revision_number: int) -> RegenerationRequest:
        if self._revisions.get(job_id, revision_number) is None:
            raise RevisionNotFoundError
        existing = self._requests.get(job_id, revision_number)
        if existing is not None:
            return existing
        return self._requests.save(
            RegenerationRequest(
                request_id=self._uuid_factory(),
                job_id=job_id,
                revision_number=revision_number,
                status=RegenerationRequestStatus.REQUESTED,
                requested_artifacts=REQUESTED_DERIVED_ARTIFACTS,
                requested_at=self._clock(),
            )
        )


def _with_request_status(
    revision: TranscriptionRevision,
    requests: RegenerationRequestRepository | None,
) -> TranscriptionRevision:
    if requests is None or requests.get(revision.job_id, revision.revision_number) is None:
        return revision
    return revision.with_derived_artifacts_status(
        DerivedArtifactsStatus.REGENERATION_REQUESTED
    )
