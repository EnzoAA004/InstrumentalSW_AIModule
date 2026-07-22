from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from saxo_ai.application.errors import (
    InvalidRevisionEventError,
    InvalidRevisionOperationError,
    RevisionConflictError,
    RevisionNotFoundError,
)
from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.application.transcription_revisions import (
    AddRevisionEvent,
    CreateTranscriptionRevision,
    DeleteRevisionEvent,
    GetTranscriptionRevision,
    GetTranscriptionRevisionHistory,
    RequestArtifactRegeneration,
    UpdateRevisionEvent,
)
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.transcription_revisions import (
    DerivedArtifactsStatus,
    EventOrigin,
    RegenerationRequestStatus,
    TranscriptionRevision,
    TranscriptionRevisionEvent,
)
from saxo_ai.infrastructure.repositories import (
    InMemoryRegenerationRequestRepository,
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)
from tests.review_helpers import JOB_ID, build_job, build_written_result

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
HUMAN_ID = UUID("22222222-2222-2222-2222-222222222222")
REQUEST_ID = UUID("33333333-3333-3333-3333-333333333333")


def fixed_clock() -> datetime:
    return NOW


def later_clock() -> datetime:
    return NOW + timedelta(seconds=1)


def fixed_human_uuid() -> UUID:
    return HUMAN_ID


def fixed_request_uuid() -> UUID:
    return REQUEST_ID


def setup_registered(
    *,
    saxophone_type: SaxophoneType = SaxophoneType.ALTO,
    events: tuple[tuple[int, int, float, float, int, float, bool], ...] | None = None,
):
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    revisions = InMemoryTranscriptionRevisionRepository()
    jobs.save(build_job(saxophone_type))
    result = build_written_result(saxophone_type=saxophone_type, events=events)
    returned = RegisterTranscriptionReview(jobs, reviews, revisions, fixed_clock).execute(
        JOB_ID, result
    )
    return jobs, reviews, revisions, result, returned


def test_registration_initializes_exact_immutable_revision_zero_once() -> None:
    jobs, reviews, revisions, result, returned = setup_registered()

    revision = revisions.get(JOB_ID, 0)
    assert returned is result
    assert reviews.get(JOB_ID) is result
    assert revision is not None
    assert revision.revision_number == 0
    assert revision.parent_revision_number is None
    assert revision.created_at == NOW
    assert revision.saxophone_type is SaxophoneType.ALTO
    assert revision.derived_artifacts_status is DerivedArtifactsStatus.CURRENT
    assert [event.event_id for event in revision.events] == ["source-0", "source-1"]
    assert [event.origin for event in revision.events] == [EventOrigin.MODEL, EventOrigin.MODEL]
    assert [event.source_index for event in revision.events] == [0, 1]
    assert revision.events[0].confidence == 0.42
    assert revision.events[0].is_low_confidence is True

    RegisterTranscriptionReview(jobs, reviews, revisions, fixed_clock).execute(JOB_ID, result)
    assert len(revisions.list(JOB_ID)) == 1
    assert revisions.get(JOB_ID, 0) is revision

    with pytest.raises(FrozenInstanceError):
        revision.revision_number = 5  # type: ignore[misc]


def test_revision_zero_supports_all_saxophones_and_empty_results() -> None:
    offsets = {
        SaxophoneType.SOPRANO: 2,
        SaxophoneType.ALTO: 9,
        SaxophoneType.TENOR: 14,
        SaxophoneType.BARITONE: 21,
    }
    for instrument, offset in offsets.items():
        _jobs, _reviews, revisions, _result, _returned = setup_registered(
            saxophone_type=instrument,
            events=((60, 60 + offset, 0.0, 0.5, 90, 0.8, False),),
        )
        revision = revisions.get(JOB_ID, 0)
        assert revision is not None
        assert revision.events[0].pitch_concert_midi == 60
        assert revision.events[0].written_pitch_midi == 60 + offset

    _jobs, _reviews, revisions, _result, _returned = setup_registered(events=())
    empty = revisions.get(JOB_ID, 0)
    assert empty is not None
    assert empty.events == ()
    assert empty.summary.event_count == 0


def test_update_add_delete_create_complete_new_revision_without_mutating_source() -> None:
    _jobs, _reviews, revisions, result, _returned = setup_registered()
    creator = CreateTranscriptionRevision(revisions, later_clock, fixed_human_uuid)

    created = creator.execute(
        JOB_ID,
        base_revision_number=0,
        operations=(
            UpdateRevisionEvent(
                "source-0", written_pitch_midi=70, onset_seconds=0.1, offset_seconds=0.6
            ),
            AddRevisionEvent(written_pitch_midi=72, onset_seconds=0.7, offset_seconds=1.0),
            DeleteRevisionEvent("source-1"),
        ),
    )

    original = revisions.get(JOB_ID, 0)
    assert original is not None
    assert [event.written_pitch_midi for event in original.events] == [69, 76]
    assert result.events[0].written_pitch_midi == 69

    assert created.revision_number == 1
    assert created.parent_revision_number == 0
    assert created.created_at == NOW + timedelta(seconds=1)
    assert created.derived_artifacts_status is DerivedArtifactsStatus.STALE
    assert [event.event_id for event in created.events] == ["source-0", f"human-{HUMAN_ID}"]
    assert created.events[0].origin is EventOrigin.MODEL
    assert created.events[0].source_index == 0
    assert created.events[0].velocity == 90
    assert created.events[0].confidence == 0.42
    assert created.events[0].is_low_confidence is True
    assert created.events[0].written_pitch_midi == 70
    assert created.events[0].pitch_concert_midi == 61
    assert created.events[0].onset_seconds == 0.1
    assert created.events[0].offset_seconds == 0.6

    human = created.events[1]
    assert human.origin is EventOrigin.HUMAN
    assert human.source_index is None
    assert human.velocity == 64
    assert human.confidence is None
    assert human.is_low_confidence is None
    assert human.written_pitch_midi == 72
    assert human.pitch_concert_midi == 63
    assert created.summary.event_count == 2
    assert created.summary.model_event_count == 1
    assert created.summary.human_event_count == 1


def test_update_preserves_position_delete_removes_and_add_appends_without_sorting() -> None:
    _jobs, _reviews, revisions, _result, _returned = setup_registered()
    creator = CreateTranscriptionRevision(revisions, later_clock, fixed_human_uuid)
    created = creator.execute(
        JOB_ID,
        base_revision_number=0,
        operations=(
            UpdateRevisionEvent(
                "source-1", written_pitch_midi=75, onset_seconds=0.05, offset_seconds=0.2
            ),
            DeleteRevisionEvent("source-0"),
            AddRevisionEvent(
                written_pitch_midi=74, onset_seconds=0.01, offset_seconds=0.1, velocity=11
            ),
        ),
    )
    assert [event.event_id for event in created.events] == ["source-1", f"human-{HUMAN_ID}"]
    assert [event.onset_seconds for event in created.events] == [0.05, 0.01]
    assert created.events[1].velocity == 11


def test_revision_operations_are_atomic_and_reject_invalid_sequences() -> None:
    _jobs, _reviews, revisions, _result, _returned = setup_registered()
    creator = CreateTranscriptionRevision(revisions, later_clock, fixed_human_uuid)

    invalid_operation_sets = (
        (),
        (
            UpdateRevisionEvent("source-0", 70, 0.1, 0.6),
            DeleteRevisionEvent("source-0"),
        ),
        (DeleteRevisionEvent("missing"),),
        (
            DeleteRevisionEvent("source-0"),
            UpdateRevisionEvent("source-0", 70, 0.1, 0.6),
        ),
    )
    for operations in invalid_operation_sets:
        with pytest.raises(InvalidRevisionOperationError):
            creator.execute(JOB_ID, base_revision_number=0, operations=operations)
        assert revisions.latest(JOB_ID).revision_number == 0
        assert len(revisions.list(JOB_ID)) == 1


@pytest.mark.parametrize(
    "operation",
    [
        UpdateRevisionEvent("source-0", -1, 0.0, 0.5),
        UpdateRevisionEvent("source-0", 128, 0.0, 0.5),
        UpdateRevisionEvent("source-0", 70, -0.1, 0.5),
        UpdateRevisionEvent("source-0", 70, 0.5, 0.5),
        AddRevisionEvent(8, 0.0, 0.5),
        AddRevisionEvent(72, float("nan"), 0.5),
        AddRevisionEvent(72, 0.0, float("inf")),
        AddRevisionEvent(72, 0.0, 0.5, velocity=128),
    ],
)
def test_authoritative_event_validation_rejects_invalid_midi_timing_and_velocity(
    operation: object,
) -> None:
    _jobs, _reviews, revisions, _result, _returned = setup_registered()
    creator = CreateTranscriptionRevision(revisions, later_clock, fixed_human_uuid)
    with pytest.raises(InvalidRevisionEventError):
        creator.execute(JOB_ID, base_revision_number=0, operations=(operation,))
    assert revisions.latest(JOB_ID).revision_number == 0


def test_history_is_sequential_and_optimistic_conflict_never_overwrites() -> None:
    _jobs, _reviews, revisions, _result, _returned = setup_registered()
    creator = CreateTranscriptionRevision(revisions, later_clock, fixed_human_uuid)
    first = creator.execute(
        JOB_ID,
        base_revision_number=0,
        operations=(UpdateRevisionEvent("source-0", 70, 0.1, 0.6),),
    )
    assert first.revision_number == 1

    with pytest.raises(RevisionConflictError):
        creator.execute(
            JOB_ID,
            base_revision_number=0,
            operations=(DeleteRevisionEvent("source-1"),),
        )

    assert revisions.latest(JOB_ID) is first
    history = GetTranscriptionRevisionHistory(revisions).execute(JOB_ID)
    assert history.latest_revision_number == 1
    assert history.revision_count == 2
    assert [summary.revision_number for summary in history.revisions] == [0, 1]
    assert history.revisions[1].parent_revision_number == 0

    assert GetTranscriptionRevision(revisions).execute(JOB_ID, 0).revision_number == 0
    with pytest.raises(RevisionNotFoundError):
        GetTranscriptionRevision(revisions).execute(JOB_ID, 99)


def test_regeneration_request_is_idempotent_marks_projection_and_creates_no_artifacts() -> None:
    _jobs, _reviews, revisions, _result, _returned = setup_registered()
    creator = CreateTranscriptionRevision(revisions, later_clock, fixed_human_uuid)
    creator.execute(
        JOB_ID,
        base_revision_number=0,
        operations=(UpdateRevisionEvent("source-0", 70, 0.1, 0.6),),
    )
    requests = InMemoryRegenerationRequestRepository()
    use_case = RequestArtifactRegeneration(revisions, requests, later_clock, fixed_request_uuid)

    first = use_case.execute(JOB_ID, 1)
    second = use_case.execute(JOB_ID, 1)

    assert first is second
    assert first.request_id == REQUEST_ID
    assert first.status is RegenerationRequestStatus.REQUESTED
    assert first.requested_artifacts == ("midi", "musicxml", "svg")
    assert not hasattr(first, "midi_bytes")
    assert not hasattr(first, "musicxml_bytes")
    assert not hasattr(first, "svg_bytes")

    detail = GetTranscriptionRevision(revisions, requests).execute(JOB_ID, 1)
    assert detail.derived_artifacts_status is DerivedArtifactsStatus.REGENERATION_REQUESTED
    stored = revisions.get(JOB_ID, 1)
    assert stored is not None
    assert stored.derived_artifacts_status is DerivedArtifactsStatus.STALE

    with pytest.raises(RevisionNotFoundError):
        use_case.execute(JOB_ID, 99)


def test_revision_event_contract_is_frozen_and_rejects_inconsistent_origin_metadata() -> None:
    with pytest.raises(InvalidRevisionEventError):
        TranscriptionRevisionEvent(
            event_id="human-bad",
            origin=EventOrigin.HUMAN,
            source_index=0,
            pitch_concert_midi=60,
            written_pitch_midi=69,
            onset_seconds=0.0,
            offset_seconds=0.5,
            velocity=64,
            confidence=0.5,
            is_low_confidence=False,
        )

    with pytest.raises(FrozenInstanceError):
        revision = TranscriptionRevision(
            job_id=JOB_ID,
            revision_number=0,
            parent_revision_number=None,
            created_at=NOW,
            saxophone_type=SaxophoneType.ALTO,
            events=(),
            derived_artifacts_status=DerivedArtifactsStatus.CURRENT,
        )
        revision.events = ()  # type: ignore[misc]
