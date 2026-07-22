from uuid import UUID

from saxo_ai.domain.models import TranscriptionJob
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
