from uuid import UUID

from saxo_ai.domain.models import JobFailureCode
from saxo_ai.domain.transcription_revisions import (
    InvalidRevisionEventError as DomainInvalidRevisionEventError,
)

InvalidRevisionEventError = DomainInvalidRevisionEventError


class UnsupportedAudioFormatError(ValueError):
    """Raised when an uploaded file extension is not supported."""


class EmptyAudioFileError(ValueError):
    """Raised when an uploaded file contains no bytes."""


class AudioSizeLimitExceededError(ValueError):
    """Raised when upload inspection observes one byte beyond the configured maximum."""

    def __init__(self, *, max_size_bytes: int, observed_size_bytes: int) -> None:
        super().__init__(
            f"Audio size exceeds {max_size_bytes} bytes; observed at least {observed_size_bytes}"
        )
        self.max_size_bytes = max_size_bytes
        self.observed_size_bytes = observed_size_bytes


class AudioDurationLimitExceededError(ValueError):
    """Raised when a valid canonical WAV is longer than the configured maximum."""

    def __init__(
        self,
        *,
        max_duration_seconds: float,
        actual_duration_seconds: float,
    ) -> None:
        super().__init__(
            "Audio duration exceeds "
            f"{max_duration_seconds:g} seconds; actual duration is {actual_duration_seconds:g}"
        )
        self.max_duration_seconds = max_duration_seconds
        self.actual_duration_seconds = actual_duration_seconds


class TranscriptionJobNotFoundError(LookupError):
    """Raised when a transcription job cannot be found."""


class TranscriptionResultNotReadyError(LookupError):
    """Raised when a known job does not yet have a produced review result."""


class TranscriptionReviewInstrumentMismatchError(ValueError):
    """Raised when a review result belongs to a different saxophone type."""


class RevisionNotFoundError(LookupError):
    """Raised when a requested immutable transcription revision does not exist."""


class RevisionConflictError(RuntimeError):
    """Raised when a writer does not target the latest transcription revision."""


class InvalidRevisionOperationError(ValueError):
    """Raised when a revision operation sequence is structurally invalid."""


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
