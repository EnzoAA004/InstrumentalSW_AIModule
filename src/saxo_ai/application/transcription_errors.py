from __future__ import annotations


class TranscriptionError(RuntimeError):
    """Base error for controlled transcription failures."""


class TranscriptionEngineUnavailableError(TranscriptionError):
    """Raised when the optional baseline runtime is unavailable or incompatible."""


class TranscriptionCheckpointDownloadError(TranscriptionError):
    """Raised when the pinned checkpoint cannot be resolved from its fixed source."""


class TranscriptionCheckpointMismatchError(TranscriptionError):
    """Raised before loading when checkpoint size or SHA-256 is not the pinned value."""

    def __init__(
        self,
        *,
        expected_sha256: str,
        actual_sha256: str | None,
        expected_size: int,
        actual_size: int | None,
    ) -> None:
        parts = ["Pinned FiloSax checkpoint verification failed"]
        if actual_size is not None:
            parts.append(f"size {actual_size} does not match expected {expected_size}")
        if actual_sha256 is not None:
            parts.append(f"SHA-256 {actual_sha256} does not match expected {expected_sha256}")
        super().__init__("; ".join(parts))
        self.expected_sha256 = expected_sha256
        self.actual_sha256 = actual_sha256
        self.expected_size = expected_size
        self.actual_size = actual_size


class TranscriptionModelInitializationError(TranscriptionError):
    """Raised when the verified checkpoint cannot initialize the pinned runtime."""


class TranscriptionInferenceError(TranscriptionError):
    """Raised when the initialized engine cannot complete inference."""


class InvalidTranscriptionEngineOutputError(TranscriptionError):
    """Raised when the external runtime output cannot become valid NoteEvent values."""

    def __init__(self, message: str, *, event_index: int | None = None) -> None:
        rendered = (
            message if event_index is None else f"Invalid event at index {event_index}: {message}"
        )
        super().__init__(rendered)
        self.event_index = event_index
