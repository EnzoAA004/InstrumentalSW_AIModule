from saxo_ai.application.ports import (
    BinaryDestination,
    BinaryStream,
    CanonicalAudioConverter,
)
from saxo_ai.domain.audio import (
    CanonicalAudioResult,
    CanonicalAudioSettings,
    OriginalAudioReference,
)


class ConvertToCanonicalAudio:
    """Application use case for producing a canonical WAV PCM artifact."""

    def __init__(self, converter: CanonicalAudioConverter) -> None:
        self._converter = converter

    def execute(
        self,
        *,
        source: BinaryStream,
        destination: BinaryDestination,
        settings: CanonicalAudioSettings,
        original: OriginalAudioReference,
    ) -> CanonicalAudioResult:
        return self._converter.convert(
            source=source,
            destination=destination,
            settings=settings,
            original=original,
        )
