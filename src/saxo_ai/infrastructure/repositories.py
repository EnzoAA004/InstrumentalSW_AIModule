from uuid import UUID

from saxo_ai.domain.models import TranscriptionJob


class InMemoryTranscriptionJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[UUID, TranscriptionJob] = {}

    def save(self, job: TranscriptionJob) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: UUID) -> TranscriptionJob | None:
        return self._jobs.get(job_id)
