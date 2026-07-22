from typing import Protocol
from uuid import UUID

from saxo_ai.domain.audio import (
    CanonicalAudioResult,
    CanonicalAudioSettings,
    OriginalAudioReference,
)
from saxo_ai.domain.models import AudioContentMetadata, TranscriptionJob
from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult


class BinaryStream(Protocol):
    def read(self, size: int) -> bytes: ...


class BinaryDestination(Protocol):
    def write(self, data: bytes) -> int | None: ...


class AudioContentHasher(Protocol):
    def inspect(self, stream: BinaryStream) -> AudioContentMetadata: ...


class CanonicalAudioConverter(Protocol):
    def convert(
        self,
        *,
        source: BinaryStream,
        destination: BinaryDestination,
        settings: CanonicalAudioSettings,
        original: OriginalAudioReference,
    ) -> CanonicalAudioResult: ...


class TranscriptionJobRepository(Protocol):
    def save(self, job: TranscriptionJob) -> None: ...

    def get(self, job_id: UUID) -> TranscriptionJob | None: ...


class TranscriptionReviewRepository(Protocol):
    def save(self, job_id: UUID, result: WrittenPitchTranscriptionResult) -> None: ...

    def get(self, job_id: UUID) -> WrittenPitchTranscriptionResult | None: ...
