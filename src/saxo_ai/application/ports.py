from typing import Protocol
from uuid import UUID

from saxo_ai.domain.models import AudioContentMetadata, TranscriptionJob


class BinaryStream(Protocol):
    def read(self, size: int) -> bytes: ...


class AudioContentHasher(Protocol):
    def inspect(self, stream: BinaryStream) -> AudioContentMetadata: ...


class TranscriptionJobRepository(Protocol):
    def save(self, job: TranscriptionJob) -> None: ...

    def get(self, job_id: UUID) -> TranscriptionJob | None: ...
