from typing import Protocol
from uuid import UUID

from saxo_ai.domain.audio import (
    CanonicalAudioResult,
    CanonicalAudioSettings,
    OriginalAudioReference,
)
from saxo_ai.domain.models import AudioContentMetadata, TranscriptionJob
from saxo_ai.domain.transcription_revisions import RegenerationRequest, TranscriptionRevision
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


class TranscriptionReviewRegistrationRepository(Protocol):
    def initialize(
        self,
        job_id: UUID,
        result: WrittenPitchTranscriptionResult,
        revision_zero: TranscriptionRevision,
    ) -> WrittenPitchTranscriptionResult: ...


class TranscriptionRevisionRepository(Protocol):
    def initialize(
        self, job_id: UUID, revision: TranscriptionRevision
    ) -> TranscriptionRevision: ...

    def latest(self, job_id: UUID) -> TranscriptionRevision | None: ...

    def get(self, job_id: UUID, revision_number: int) -> TranscriptionRevision | None: ...

    def list(self, job_id: UUID) -> tuple[TranscriptionRevision, ...]: ...

    def append(
        self,
        job_id: UUID,
        expected_latest_revision: int,
        revision: TranscriptionRevision,
    ) -> None: ...


class RegenerationRequestRepository(Protocol):
    def get(self, job_id: UUID, revision_number: int) -> RegenerationRequest | None: ...

    def save(self, request: RegenerationRequest) -> RegenerationRequest: ...
