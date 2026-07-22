from datetime import UTC, datetime
from uuid import UUID

import pytest

from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.domain.transcription_revisions import TranscriptionRevision
from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult
from saxo_ai.infrastructure.repositories import (
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)
from tests.review_helpers import JOB_ID, build_job, build_written_result

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return NOW


class SimulatedAtomicInitializationFailure(RuntimeError):
    pass


class FailingReviewRegistrationRepository:
    def __init__(self) -> None:
        self.calls = 0

    def initialize(
        self,
        job_id: UUID,
        result: WrittenPitchTranscriptionResult,
        revision_zero: TranscriptionRevision,
    ) -> WrittenPitchTranscriptionResult:
        self.calls += 1
        assert job_id == JOB_ID
        assert revision_zero.revision_number == 0
        assert revision_zero.events[0].written_pitch_midi == result.events[0].written_pitch_midi
        raise SimulatedAtomicInitializationFailure


def test_registration_failure_leaves_no_partial_review_or_revision_zero() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    revisions = InMemoryTranscriptionRevisionRepository()
    registration = FailingReviewRegistrationRepository()
    job = build_job()
    result = build_written_result()
    jobs.save(job)

    with pytest.raises(SimulatedAtomicInitializationFailure):
        RegisterTranscriptionReview(jobs, registration, fixed_clock).execute(JOB_ID, result)

    assert registration.calls == 1
    assert reviews.get(JOB_ID) is None
    assert revisions.list(JOB_ID) == ()
    assert jobs.get(JOB_ID) is job
