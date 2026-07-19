class UnsupportedAudioFormatError(ValueError):
    """Raised when an uploaded file extension is not supported."""


class EmptyAudioFileError(ValueError):
    """Raised when an uploaded file contains no bytes."""


class TranscriptionJobNotFoundError(LookupError):
    """Raised when a transcription job cannot be found."""
