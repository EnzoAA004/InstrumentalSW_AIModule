from uuid import UUID

import pytest

from saxo_ai.application.errors import (
    TranscriptionJobNotFoundError,
    TranscriptionResultNotReadyError,
    TranscriptionReviewInstrumentMismatchError,
)
from saxo_ai.application.transcription_review import (
    GetTranscriptionReview,
    RegisterTranscriptionReview,
)
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.infrastructure.repositories import (
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRegistrationRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)
from tests.review_helpers import JOB_ID, build_job, build_written_result


def registration_repository(
    reviews: InMemoryTranscriptionReviewRepository,
) -> InMemoryTranscriptionReviewRegistrationRepository:
    return InMemoryTranscriptionReviewRegistrationRepository(
        reviews, InMemoryTranscriptionRevisionRepository()
    )


def registration_repository(
    reviews: InMemoryTranscriptionReviewRepository,
) -> InMemoryTranscriptionReviewRegistrationRepository:
    return InMemoryTranscriptionReviewRegistrationRepository(
        reviews, InMemoryTranscriptionRevisionRepository()
    )


def test_review_repository_preserves_exact_result_reference() -> None:
    repository = InMemoryTranscriptionReviewRepository()
    result = build_written_result()

    repository.save(JOB_ID, result)

    assert repository.get(JOB_ID) is result
    assert repository.get(UUID("22222222-2222-2222-2222-222222222222")) is None


def test_register_requires_existing_job_and_matching_instrument() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    register = RegisterTranscriptionReview(jobs, registration_repository(reviews))
    result = build_written_result()

    with pytest.raises(TranscriptionJobNotFoundError):
        register.execute(JOB_ID, result)

    jobs.save(build_job(SaxophoneType.TENOR))
    with pytest.raises(TranscriptionReviewInstrumentMismatchError):
        register.execute(JOB_ID, result)
    assert reviews.get(JOB_ID) is None


def test_register_and_get_preserve_identity_and_build_exact_ordered_view() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    job = build_job()
    result = build_written_result()
    jobs.save(job)

    stored = RegisterTranscriptionReview(jobs, registration_repository(reviews)).execute(
        JOB_ID, result
    )
    snapshot = GetTranscriptionReview(jobs, reviews).execute(JOB_ID)

    assert stored is result
    assert reviews.get(JOB_ID) is result
    assert snapshot.job_id == JOB_ID
    assert snapshot.schema_version == "1.0"
    assert snapshot.note_event_schema_version == "1.0"
    assert snapshot.low_confidence_policy_version == "1.0"
    assert snapshot.written_pitch_policy_version == "1.0"
    assert snapshot.saxophone_type is SaxophoneType.ALTO
    assert snapshot.low_confidence_threshold == 0.5
    assert snapshot.confidence_interpretation == "model_signal_not_calibrated_accuracy"
    assert snapshot.confidence_method == "model_probability"
    assert snapshot.summary.event_count == 2
    assert snapshot.summary.low_confidence_count == 1
    assert [event.index for event in snapshot.events] == [0, 1]
    assert [event.pitch_concert_midi for event in snapshot.events] == [60, 67]
    assert [event.written_pitch_midi for event in snapshot.events] == [69, 76]
    assert [event.onset_seconds for event in snapshot.events] == [0.0, 0.25]
    assert [event.offset_seconds for event in snapshot.events] == [0.5, 1.0]
    assert [event.velocity for event in snapshot.events] == [90, 100]
    assert [event.confidence for event in snapshot.events] == [0.42, 0.82]
    assert [event.is_low_confidence for event in snapshot.events] == [True, False]


def test_get_distinguishes_unknown_job_from_not_ready() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    get_review = GetTranscriptionReview(jobs, reviews)

    with pytest.raises(TranscriptionJobNotFoundError):
        get_review.execute(JOB_ID)

    jobs.save(build_job())
    with pytest.raises(TranscriptionResultNotReadyError):
        get_review.execute(JOB_ID)


@pytest.mark.parametrize("threshold", [0.0, 1.0])
@pytest.mark.parametrize("saxophone_type", list(SaxophoneType))
def test_empty_review_is_valid_for_thresholds_and_all_saxophones(
    threshold: float,
    saxophone_type: SaxophoneType,
) -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    jobs.save(build_job(saxophone_type))
    result = build_written_result(saxophone_type=saxophone_type, threshold=threshold, events=())
    RegisterTranscriptionReview(jobs, registration_repository(reviews)).execute(JOB_ID, result)

    snapshot = GetTranscriptionReview(jobs, reviews).execute(JOB_ID)

    assert snapshot.saxophone_type is saxophone_type
    assert snapshot.low_confidence_threshold == threshold
    assert snapshot.summary.event_count == 0
    assert snapshot.summary.low_confidence_count == 0
    assert snapshot.events == ()


def test_review_view_is_deterministic() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    jobs.save(build_job())
    RegisterTranscriptionReview(jobs, registration_repository(reviews)).execute(
        JOB_ID, build_written_result()
    )
    get_review = GetTranscriptionReview(jobs, reviews)

    assert get_review.execute(JOB_ID) == get_review.execute(JOB_ID)
