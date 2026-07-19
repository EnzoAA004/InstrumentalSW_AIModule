from typing import Protocol
from uuid import UUID

from saxo_ai.domain.models import TranscriptionJob


class TranscriptionJobRepository(Protocol):
    def save(self, job: TranscriptionJob) -> None: ...

    def get(self, job_id: UUID) -> TranscriptionJob | None: ...
