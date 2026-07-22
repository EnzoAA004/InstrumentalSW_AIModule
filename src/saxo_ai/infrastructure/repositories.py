from uuid import UUID

from saxo_ai.application.errors import RevisionConflictError
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


class InMemoryTranscriptionReviewRepository:
    def __init__(self) -> None:
        self._results: dict[UUID, WrittenPitchTranscriptionResult] = {}

    def save(self, job_id: UUID, result: WrittenPitchTranscriptionResult) -> None:
        self._results[job_id] = result

    def get(self, job_id: UUID) -> WrittenPitchTranscriptionResult | None:
        return self._results.get(job_id)


class InMemoryTranscriptionRevisionRepository:
    def __init__(self) -> None:
        self._revisions: dict[UUID, tuple[TranscriptionRevision, ...]] = {}

    def initialize(self, job_id: UUID, revision: TranscriptionRevision) -> TranscriptionRevision:
        existing = self._revisions.get(job_id)
        if existing is not None:
            return existing[0]
        if revision.job_id != job_id or revision.revision_number != 0:
            raise ValueError("revision initialization requires matching revision zero")
        self._revisions[job_id] = (revision,)
        return revision

    def latest(self, job_id: UUID) -> TranscriptionRevision | None:
        revisions = self._revisions.get(job_id, ())
        return revisions[-1] if revisions else None

    def get(self, job_id: UUID, revision_number: int) -> TranscriptionRevision | None:
        revisions = self._revisions.get(job_id, ())
        if (
            isinstance(revision_number, bool)
            or not isinstance(revision_number, int)
            or revision_number < 0
            or revision_number >= len(revisions)
        ):
            return None
        return revisions[revision_number]

    def list(self, job_id: UUID) -> tuple[TranscriptionRevision, ...]:
        return self._revisions.get(job_id, ())

    def append(
        self,
        job_id: UUID,
        expected_latest_revision: int,
        revision: TranscriptionRevision,
    ) -> None:
        current = self._revisions.get(job_id, ())
        if not current or current[-1].revision_number != expected_latest_revision:
            raise RevisionConflictError
        if revision.job_id != job_id:
            raise ValueError("revision job_id must match repository key")
        if revision.revision_number != expected_latest_revision + 1:
            raise ValueError("revision number must follow expected latest revision")
        self._revisions[job_id] = (*current, revision)


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
