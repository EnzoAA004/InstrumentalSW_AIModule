from uuid import UUID

from saxo_ai.domain.models import JobFailureCode


class UnsupportedAudioFormatError(ValueError):
    """Raised when an uploaded file extension is not supported."""


class EmptyAudioFileError(ValueError):
    """Raised when an uploaded file contains no bytes."""


class TranscriptionJobNotFoundError(LookupError):
    """Raised when a transcription job cannot be found."""


class FfmpegNotAvailableError(RuntimeError):
    """Raised when the FFmpeg executable cannot be started."""


class FfmpegTimeoutError(TimeoutError):
    """Raised when an FFmpeg command exceeds its configured timeout."""


class FfmpegConversionError(RuntimeError):
    """Raised when a non-content FFmpeg command exits unsuccessfully."""

    def __init__(self, *, return_code: int, stderr: str) -> None:
        super().__init__(f"FFmpeg command failed with return code {return_code}: {stderr}")
        self.return_code = return_code
        self.stderr = stderr


class AudioContentInvalidError(FfmpegConversionError):
    """Raised only when FFmpeg cannot decode the supplied audio content."""


class CanonicalAudioOutputMissingError(RuntimeError):
    """Raised when FFmpeg reports success without producing an output artifact."""


class CanonicalAudioOutputInvalidError(RuntimeError):
    """Raised when the produced artifact is not the requested canonical WAV."""


class TranscriptionAudioValidationError(RuntimeError):
    """Stable application error for a transcription with invalid audio content."""

    def __init__(self, *, job_id: UUID, failure_code: JobFailureCode) -> None:
        super().__init__(
            f"Transcription job {job_id} failed audio validation with {failure_code.value}"
        )
        self.job_id = job_id
        self.failure_code = failure_code
