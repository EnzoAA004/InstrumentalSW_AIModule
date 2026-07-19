from pathlib import Path
from uuid import UUID, uuid4

from saxo_ai.application.errors import (
    EmptyAudioFileError,
    TranscriptionJobNotFoundError,
    UnsupportedAudioFormatError,
)
from saxo_ai.application.ports import AudioContentHasher, BinaryStream, TranscriptionJobRepository
from saxo_ai.domain.models import InputMode, JobStatus, SaxophoneType, TranscriptionJob

_ALLOWED_EXTENSIONS = {".mp3", ".wav"}


class CreateTranscriptionJob:
    def __init__(
        self,
        repository: TranscriptionJobRepository,
        content_hasher: AudioContentHasher,
    ) -> None:
        self._repository = repository
        self._content_hasher = content_hasher

    def execute(
        self,
        *,
        filename: str,
        content: BinaryStream,
        saxophone_type: SaxophoneType,
        input_mode: InputMode,
    ) -> TranscriptionJob:
        if Path(filename).suffix.lower() not in _ALLOWED_EXTENSIONS:
            raise UnsupportedAudioFormatError

        metadata = self._content_hasher.inspect(content)
        if metadata.size_bytes == 0:
            raise EmptyAudioFileError

        job = TranscriptionJob(
            job_id=uuid4(),
            status=JobStatus.UPLOADED,
            filename=filename,
            size_bytes=metadata.size_bytes,
            audio_sha256=metadata.audio_sha256,
            saxophone_type=saxophone_type,
            input_mode=input_mode,
        )
        self._repository.save(job)
        return job


class GetTranscriptionJob:
    def __init__(self, repository: TranscriptionJobRepository) -> None:
        self._repository = repository

    def execute(self, job_id: UUID) -> TranscriptionJob:
        job = self._repository.get(job_id)
        if job is None:
            raise TranscriptionJobNotFoundError
        return job
