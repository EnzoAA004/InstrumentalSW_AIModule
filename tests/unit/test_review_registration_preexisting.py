from datetime import UTC, datetime

import pytest

from saxo_ai.application.errors import TranscriptionReviewInstrumentMismatchError
from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.infrastructure.repositories import (
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRegistrationRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)
from tests.review_helpers import JOB_ID, build_job, build_written_result

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def fixed_clock() -> datetime:
    return NOW


def test_registration_requires_revision_zero_for_preexisting_review() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    revisions = InMemoryTranscriptionRevisionRepository()
    registrations = InMemoryTranscriptionReviewRegistrationRepository(reviews, revisions)
    job = build_job()
    result = build_written_result()
    source_events = result.events
    jobs.save(job)
    reviews.save(JOB_ID, result)

    use_case = RegisterTranscriptionReview(jobs, registrations, fixed_clock)
    returned = use_case.execute(JOB_ID, result)
    repeated = use_case.execute(JOB_ID, result)

    assert returned is result
    assert repeated is result
    assert reviews.get(JOB_ID) is result
    assert len(revisions.list(JOB_ID)) == 1
    revision_zero = revisions.get(JOB_ID, 0)
    assert revision_zero is not None
    assert revision_zero.revision_number == 0
    assert revision_zero.events[0].written_pitch_midi == result.events[0].written_pitch_midi
    assert result.events is source_events
    assert jobs.get(JOB_ID) is job

    different_instance = build_written_result()
    assert different_instance is not result
    with pytest.raises(TranscriptionReviewInstrumentMismatchError):
        use_case.execute(JOB_ID, different_instance)

    assert reviews.get(JOB_ID) is result
    assert revisions.list(JOB_ID) == (revision_zero,)
    assert jobs.get(JOB_ID) is job
