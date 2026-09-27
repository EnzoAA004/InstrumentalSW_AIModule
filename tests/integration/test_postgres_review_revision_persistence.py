from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from tests.review_helpers import JOB_ID, build_job, build_written_result

from saxo_ai.application.errors import (
    RevisionConflictError,
    TranscriptionReviewInstrumentMismatchError,
)
from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.application.transcription_revisions import (
    AddRevisionEvent,
    CreateTranscriptionRevision,
    GetTranscriptionRevision,
    GetTranscriptionRevisionHistory,
    RequestArtifactRegeneration,
    UpdateRevisionEvent,
    build_revision_zero,
)
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.transcription_revisions import (
    DerivedArtifactsStatus,
    RegenerationRequestStatus,
)
from saxo_ai.infrastructure.postgres_review_revision_repository import (
    PostgresRegenerationRequestRepository,
    PostgresTranscriptionReviewRegistrationRepository,
    PostgresTranscriptionReviewRepository,
    PostgresTranscriptionRevisionRepository,
)
from saxo_ai.infrastructure.postgres_transcription_job_repository import (
    PostgresTranscriptionJobRepository,
)

pytestmark = pytest.mark.postgres_integration

NOW = datetime(2026, 9, 27, 19, 0, tzinfo=UTC)
LATER = NOW + timedelta(seconds=1)
HUMAN_ID = UUID("22222222-2222-2222-2222-222222222222")
REQUEST_ID = UUID("33333333-3333-3333-3333-333333333333")


def _clock() -> datetime:
    return NOW


def _later_clock() -> datetime:
    return LATER


def _human_uuid() -> UUID:
    return HUMAN_ID


def _request_uuid() -> UUID:
    return REQUEST_ID


def _save_job(engine: Engine, *, job_id: UUID = JOB_ID) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("delete from transcription_jobs where job_id = :job_id"), {"job_id": job_id}
        )
    PostgresTranscriptionJobRepository(engine).save(replace(build_job(), job_id=job_id))


def _repositories(
    engine: Engine,
) -> tuple[
    PostgresTranscriptionReviewRepository,
    PostgresTranscriptionRevisionRepository,
    PostgresTranscriptionReviewRegistrationRepository,
    PostgresRegenerationRequestRepository,
]:
    reviews = PostgresTranscriptionReviewRepository(engine)
    revisions = PostgresTranscriptionRevisionRepository(engine)
    registrations = PostgresTranscriptionReviewRegistrationRepository(engine)
    requests = PostgresRegenerationRequestRepository(engine)
    return reviews, revisions, registrations, requests


def _register_review(engine: Engine) -> None:
    _save_job(engine)
    _reviews, _revisions, registrations, _requests = _repositories(engine)
    RegisterTranscriptionReview(
        PostgresTranscriptionJobRepository(engine),
        registrations,
        _clock,
    ).execute(JOB_ID, build_written_result())


def test_review_and_revision_zero_survive_new_repository_instances(
    postgres_engine: Engine,
) -> None:
    _register_review(postgres_engine)

    reviews, revisions, _registrations, _requests = _repositories(postgres_engine)
    review = reviews.get(JOB_ID)
    revision = revisions.get(JOB_ID, 0)

    assert review is not None
    assert [event.written_pitch_midi for event in review.events] == [69, 76]
    assert revision is not None
    assert revision.revision_number == 0
    assert revision.created_at == NOW
    assert revision.saxophone_type is SaxophoneType.ALTO
    assert [event.event_id for event in revision.events] == ["source-0", "source-1"]
    assert [event.confidence for event in revision.events] == [0.42, 0.82]
    assert [event.is_low_confidence for event in revision.events] == [True, False]


def test_revision_zero_initialization_is_atomic_on_write_failure(
    postgres_engine: Engine,
) -> None:
    _save_job(postgres_engine)
    _reviews, _revisions, registrations, _requests = _repositories(postgres_engine)
    result = build_written_result()

    with pytest.raises(RuntimeError, match="simulated failure"):
        registrations.initialize(
            JOB_ID,
            result,
            revision_zero=build_revision_zero(JOB_ID, result, NOW),
            fail_after_review_for_test=True,
        )

    reviews, revisions, _registrations, _requests = _repositories(postgres_engine)
    assert reviews.get(JOB_ID) is None
    assert revisions.get(JOB_ID, 0) is None


def test_revision_history_is_immutable_sequential_and_rejects_stale_writers(
    postgres_engine: Engine,
) -> None:
    _register_review(postgres_engine)
    _reviews, revisions, _registrations, _requests = _repositories(postgres_engine)
    creator = CreateTranscriptionRevision(revisions, _later_clock, _human_uuid)

    first = creator.execute(
        JOB_ID,
        base_revision_number=0,
        operations=(
            UpdateRevisionEvent("source-0", 70, 0.1, 0.6),
            AddRevisionEvent(72, 0.7, 1.0),
        ),
    )

    assert first.revision_number == 1
    with pytest.raises(RevisionConflictError):
        creator.execute(
            JOB_ID,
            base_revision_number=0,
            operations=(UpdateRevisionEvent("source-1", 77, 0.3, 1.1),),
        )

    second = creator.execute(
        JOB_ID,
        base_revision_number=1,
        operations=(UpdateRevisionEvent("source-1", 77, 0.3, 1.1),),
    )

    history = GetTranscriptionRevisionHistory(revisions).execute(JOB_ID)
    assert second.revision_number == 2
    assert [entry.revision_number for entry in history.revisions] == [0, 1, 2]
    assert GetTranscriptionRevision(revisions).execute(JOB_ID, 0).events[0].written_pitch_midi == 69
    assert GetTranscriptionRevision(revisions).execute(JOB_ID, 1).events[0].written_pitch_midi == 70
    assert GetTranscriptionRevision(revisions).execute(JOB_ID, 2).events[1].written_pitch_midi == 77


def test_regeneration_request_is_durable_and_idempotent(postgres_engine: Engine) -> None:
    _register_review(postgres_engine)
    _reviews, revisions, _registrations, requests = _repositories(postgres_engine)
    CreateTranscriptionRevision(revisions, _later_clock, _human_uuid).execute(
        JOB_ID,
        base_revision_number=0,
        operations=(UpdateRevisionEvent("source-0", 70, 0.1, 0.6),),
    )
    use_case = RequestArtifactRegeneration(revisions, requests, _later_clock, _request_uuid)

    first = use_case.execute(JOB_ID, 1)
    second = RequestArtifactRegeneration(
        PostgresTranscriptionRevisionRepository(postgres_engine),
        PostgresRegenerationRequestRepository(postgres_engine),
        _later_clock,
        uuid4,
    ).execute(JOB_ID, 1)

    assert first == second
    assert first.request_id == REQUEST_ID
    assert first.status is RegenerationRequestStatus.REQUESTED
    detail = GetTranscriptionRevision(
        PostgresTranscriptionRevisionRepository(postgres_engine),
        PostgresRegenerationRequestRepository(postgres_engine),
    ).execute(JOB_ID, 1)
    assert detail.derived_artifacts_status is DerivedArtifactsStatus.REGENERATION_REQUESTED


def test_database_constraints_reject_orphan_review_revision_and_request(
    postgres_engine: Engine,
) -> None:
    missing_job_id = uuid4()
    missing_request_id = uuid4()

    with pytest.raises(IntegrityError), postgres_engine.begin() as connection:
        connection.execute(
            text(
                "insert into transcription_reviews "
                "(job_id, saxophone_type, low_confidence_threshold, confidence_method, "
                "engine_name, engine_version, engine_source_revision, model_id, "
                "model_revision, checkpoint_filename, checkpoint_sha256, sample_rate_hz, "
                "device, onset_threshold, offset_threshold, frame_threshold) "
                "values (:job_id, 'alto', 0.5, 'model_probability', 'engine', '1.0', "
                "'0123456789012345678901234567890123456789', 'model', 'rev', "
                "'checkpoint.pt', "
                "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', "
                "44100, 'cpu', 0.5, 0.5, 0.5)"
            ),
            {"job_id": missing_job_id},
        )

    with pytest.raises(IntegrityError), postgres_engine.begin() as connection:
        connection.execute(
            text(
                "insert into transcription_revisions "
                "(job_id, revision_number, parent_revision_number, created_at, "
                "saxophone_type, derived_artifacts_status) "
                "values (:job_id, 0, null, :created_at, 'alto', 'CURRENT')"
            ),
            {"job_id": missing_job_id, "created_at": NOW},
        )

    with pytest.raises(IntegrityError), postgres_engine.begin() as connection:
        connection.execute(
            text(
                "insert into regeneration_requests "
                "(request_id, job_id, revision_number, status, requested_artifacts, "
                "requested_at) "
                "values (:request_id, :job_id, 0, 'REQUESTED', 'midi,musicxml,svg', "
                ":requested_at)"
            ),
            {
                "request_id": missing_request_id,
                "job_id": missing_job_id,
                "requested_at": NOW,
            },
        )


def test_duplicate_registration_is_idempotent_but_different_review_is_rejected(
    postgres_engine: Engine,
) -> None:
    _save_job(postgres_engine)
    _reviews, _revisions, registrations, _requests = _repositories(postgres_engine)
    register = RegisterTranscriptionReview(
        PostgresTranscriptionJobRepository(postgres_engine),
        registrations,
        _clock,
    )
    result = build_written_result()
    returned = register.execute(JOB_ID, result)
    repeated = register.execute(JOB_ID, result)

    assert returned == repeated
    assert len(PostgresTranscriptionRevisionRepository(postgres_engine).list(JOB_ID)) == 1

    with pytest.raises(TranscriptionReviewInstrumentMismatchError):
        register.execute(JOB_ID, build_written_result(threshold=0.25))
