from typing import NoReturn
from uuid import UUID

from saxo_ai.application.errors import (
    AudioContentInvalidError,
    AudioDurationLimitExceededError,
    TranscriptionAudioValidationError,
    TranscriptionJobNotFoundError,
)
from saxo_ai.application.ports import (
    BinaryDestination,
    BinaryStream,
    CanonicalAudioConverter,
    TranscriptionJobRepository,
)
from saxo_ai.domain.audio import (
    CanonicalAudioResult,
    CanonicalAudioSettings,
    OriginalAudioReference,
)
from saxo_ai.domain.models import JobFailureCode, TranscriptionJob


class ValidateTranscriptionAudio:
    """Validate a stored transcription's trusted source through canonical conversion."""

    def __init__(
        self,
        repository: TranscriptionJobRepository,
        converter: CanonicalAudioConverter,
    ) -> None:
        self._repository = repository
        self._converter = converter

    def execute(
        self,
        *,
        job_id: UUID,
        source: BinaryStream,
        destination: BinaryDestination,
        settings: CanonicalAudioSettings,
    ) -> CanonicalAudioResult:
        job = self._repository.get(job_id)
        if job is None:
            raise TranscriptionJobNotFoundError

        original = OriginalAudioReference(
            filename=job.filename,
            size_bytes=job.size_bytes,
            audio_sha256=job.audio_sha256,
        )

        try:
            return self._converter.convert(
                source=source,
                destination=destination,
                settings=settings,
                original=original,
            )
        except AudioContentInvalidError as error:
            self._raise_failed_job(
                job=job,
                failure_code=JobFailureCode.AUDIO_CONTENT_INVALID,
                error=error,
            )
        except AudioDurationLimitExceededError as error:
            self._raise_failed_job(
                job=job,
                failure_code=JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED,
                error=error,
            )

    def _raise_failed_job(
        self,
        *,
        job: TranscriptionJob,
        failure_code: JobFailureCode,
        error: Exception,
    ) -> NoReturn:
        self._repository.save(job.mark_failed(failure_code))
        raise TranscriptionAudioValidationError(
            job_id=job.job_id,
            failure_code=failure_code,
        ) from error
