from dataclasses import dataclass
from threading import RLock
from uuid import UUID

from saxo_ai.application.errors import (
    RevisionConflictError,
    TranscriptionReviewInstrumentMismatchError,
)
from saxo_ai.domain.models import TranscriptionJob
from saxo_ai.domain.transcription_revisions import RegenerationRequest, TranscriptionRevision
from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult


class InMemoryTranscriptionJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[UUID, TranscriptionJob] = {}

    def save(self, job: TranscriptionJob) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: UUID) -> TranscriptionJob | None:
        return self._jobs.get(job_id)


@dataclass(frozen=True, slots=True)
class _ReviewRevisionSnapshot:
    reviews: dict[UUID, WrittenPitchTranscriptionResult]
    revisions: dict[UUID, tuple[TranscriptionRevision, ...]]


class _ReviewRevisionStore:
    def __init__(self, snapshot: _ReviewRevisionSnapshot | None = None) -> None:
        self.lock = RLock()
        self.snapshot = snapshot or _ReviewRevisionSnapshot(reviews={}, revisions={})


class InMemoryTranscriptionReviewRepository:
    def __init__(self) -> None:
        self._store = _ReviewRevisionStore()

    def save(self, job_id: UUID, result: WrittenPitchTranscriptionResult) -> None:
        with self._store.lock:
            snapshot = self._store.snapshot
            reviews = dict(snapshot.reviews)
            reviews[job_id] = result
            self._store.snapshot = _ReviewRevisionSnapshot(
                reviews=reviews,
                revisions=snapshot.revisions,
            )

    def get(self, job_id: UUID) -> WrittenPitchTranscriptionResult | None:
        with self._store.lock:
            return self._store.snapshot.reviews.get(job_id)


class InMemoryTranscriptionRevisionRepository:
    def __init__(self) -> None:
        self._store = _ReviewRevisionStore()

    def initialize(self, job_id: UUID, revision: TranscriptionRevision) -> TranscriptionRevision:
        if revision.job_id != job_id or revision.revision_number != 0:
            raise ValueError("revision initialization requires matching revision zero")
        with self._store.lock:
            snapshot = self._store.snapshot
            existing = snapshot.revisions.get(job_id)
            if existing is not None:
                return existing[0]
            revisions = dict(snapshot.revisions)
            revisions[job_id] = (revision,)
            self._store.snapshot = _ReviewRevisionSnapshot(
                reviews=snapshot.reviews,
                revisions=revisions,
            )
            return revision

    def latest(self, job_id: UUID) -> TranscriptionRevision | None:
        with self._store.lock:
            revisions = self._store.snapshot.revisions.get(job_id, ())
            return revisions[-1] if revisions else None

    def get(self, job_id: UUID, revision_number: int) -> TranscriptionRevision | None:
        with self._store.lock:
            revisions = self._store.snapshot.revisions.get(job_id, ())
            if (
                isinstance(revision_number, bool)
                or not isinstance(revision_number, int)
                or revision_number < 0
                or revision_number >= len(revisions)
            ):
                return None
            return revisions[revision_number]

    def list(self, job_id: UUID) -> tuple[TranscriptionRevision, ...]:
        with self._store.lock:
            return self._store.snapshot.revisions.get(job_id, ())

    def append(
        self,
        job_id: UUID,
        expected_latest_revision: int,
        revision: TranscriptionRevision,
    ) -> None:
        with self._store.lock:
            snapshot = self._store.snapshot
            current = snapshot.revisions.get(job_id, ())
            if not current or current[-1].revision_number != expected_latest_revision:
                raise RevisionConflictError
            if revision.job_id != job_id:
                raise ValueError("revision job_id must match repository key")
            if revision.revision_number != expected_latest_revision + 1:
                raise ValueError("revision number must follow expected latest revision")
            revisions = dict(snapshot.revisions)
            revisions[job_id] = (*current, revision)
            self._store.snapshot = _ReviewRevisionSnapshot(
                reviews=snapshot.reviews,
                revisions=revisions,
            )


class InMemoryTranscriptionReviewRegistrationRepository:
    def __init__(
        self,
        reviews: InMemoryTranscriptionReviewRepository,
        revisions: InMemoryTranscriptionRevisionRepository,
    ) -> None:
        self._store = _bind_shared_store(reviews, revisions)

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

        with self._store.lock:
            snapshot = self._store.snapshot
            existing_review = snapshot.reviews.get(job_id)
            existing_revisions = snapshot.revisions.get(job_id, ())

            if existing_review is not None and existing_review is not result:
                raise TranscriptionReviewInstrumentMismatchError
            if existing_revisions and not _same_revision_source(
                existing_revisions[0], revision_zero
            ):
                raise TranscriptionReviewInstrumentMismatchError

            registered_review = existing_review or result
            registered_revisions = existing_revisions or (revision_zero,)
            if existing_review is not None and existing_revisions:
                return existing_review

            reviews = dict(snapshot.reviews)
            reviews[job_id] = registered_review
            revisions = dict(snapshot.revisions)
            revisions[job_id] = registered_revisions
            self._store.snapshot = _ReviewRevisionSnapshot(
                reviews=reviews,
                revisions=revisions,
            )
            return registered_review


def _bind_shared_store(
    reviews: InMemoryTranscriptionReviewRepository,
    revisions: InMemoryTranscriptionRevisionRepository,
) -> _ReviewRevisionStore:
    review_store = reviews._store
    revision_store = revisions._store
    if review_store is revision_store:
        return review_store

    with review_store.lock, revision_store.lock:
        merged_reviews = dict(review_store.snapshot.reviews)
        for job_id, result in revision_store.snapshot.reviews.items():
            existing_review = merged_reviews.get(job_id)
            if existing_review is not None and existing_review is not result:
                raise TranscriptionReviewInstrumentMismatchError
            merged_reviews[job_id] = result

        merged_revisions = dict(review_store.snapshot.revisions)
        for job_id, history in revision_store.snapshot.revisions.items():
            existing_history = merged_revisions.get(job_id)
            if existing_history is not None and existing_history != history:
                raise ValueError("cannot bind incompatible revision repositories")
            merged_revisions[job_id] = history

        shared = _ReviewRevisionStore(
            _ReviewRevisionSnapshot(
                reviews=merged_reviews,
                revisions=merged_revisions,
            )
        )
        reviews._store = shared
        revisions._store = shared
        return shared


def _same_revision_source(
    existing: TranscriptionRevision,
    candidate: TranscriptionRevision,
) -> bool:
    return (
        existing.job_id == candidate.job_id
        and existing.revision_number == 0
        and existing.parent_revision_number is None
        and existing.saxophone_type is candidate.saxophone_type
        and existing.events == candidate.events
        and existing.derived_artifacts_status is candidate.derived_artifacts_status
        and existing.schema_version == candidate.schema_version
    )


class InMemoryRegenerationRequestRepository:
    def __init__(self) -> None:
        self._requests: dict[tuple[UUID, int], RegenerationRequest] = {}

    def get(self, job_id: UUID, revision_number: int) -> RegenerationRequest | None:
        return self._requests.get((job_id, revision_number))

    def save(self, request: RegenerationRequest) -> RegenerationRequest:
        key = (request.job_id, request.revision_number)
        existing = self._requests.get(key)
        if existing is not None:
            return existing
        self._requests[key] = request
        return request


from saxo_ai.infrastructure.revision_artifact_repository import (  # noqa: E402
    InMemoryRevisionArtifactRepository,
)

__all__ = ["InMemoryRevisionArtifactRepository"]
