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
    """Raised when FFmpeg exits unsuccessfully."""

    def __init__(self, *, return_code: int, stderr: str) -> None:
        super().__init__(f"FFmpeg conversion failed with return code {return_code}: {stderr}")
        self.return_code = return_code
        self.stderr = stderr


class CanonicalAudioOutputMissingError(RuntimeError):
    """Raised when FFmpeg reports success without producing an output artifact."""


class CanonicalAudioOutputInvalidError(RuntimeError):
    """Raised when the produced artifact is not the requested canonical WAV."""
