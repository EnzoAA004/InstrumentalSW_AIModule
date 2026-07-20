from __future__ import annotations

import math
import re
from dataclasses import dataclass

_DEFAULT_SCHEMA_VERSION = "1.0"
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")

DEFAULT_MAX_AUDIO_SIZE_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_AUDIO_DURATION_SECONDS = 15 * 60.0


@dataclass(frozen=True, slots=True)
class AudioProcessingLimits:
    """Runtime-independent resource limits for accepted audio processing."""

    max_size_bytes: int = DEFAULT_MAX_AUDIO_SIZE_BYTES
    max_duration_seconds: float = DEFAULT_MAX_AUDIO_DURATION_SECONDS

    def __post_init__(self) -> None:
        if isinstance(self.max_size_bytes, bool) or not isinstance(self.max_size_bytes, int):
            raise TypeError("max_size_bytes must be an integer")
        if self.max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be greater than zero")

        if isinstance(self.max_duration_seconds, bool) or not isinstance(
            self.max_duration_seconds, (int, float)
        ):
            raise TypeError("max_duration_seconds must be numeric")
        duration = float(self.max_duration_seconds)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("max_duration_seconds must be finite and greater than zero")
        object.__setattr__(self, "max_duration_seconds", duration)


class InvalidCanonicalAudioSettingsError(ValueError):
    """Raised when canonical audio settings are not supported."""


@dataclass(frozen=True, slots=True)
class OriginalAudioReference:
    """Logical, path-free reference to the original uploaded content."""

    filename: str
    size_bytes: int
    audio_sha256: str

    def __post_init__(self) -> None:
        if self.size_bytes < 0:
            raise ValueError("size_bytes must not be negative")
        if _SHA256_PATTERN.fullmatch(self.audio_sha256) is None:
            raise ValueError("audio_sha256 must be a lowercase 64-character hexadecimal digest")


@dataclass(frozen=True, slots=True)
class CanonicalAudioSettings:
    """Versioned settings for the fixed WAV PCM canonical representation."""

    sample_rate_hz: int = 16_000
    channels: int = 1
    container: str = "wav"
    codec: str = "pcm_s16le"
    sample_width_bits: int = 16
    amplitude_normalization: str = "none"
    schema_version: str = _DEFAULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise InvalidCanonicalAudioSettingsError("sample_rate_hz must be greater than zero")
        if self.channels not in {1, 2}:
            raise InvalidCanonicalAudioSettingsError("channels must be either 1 or 2")
        if self.container != "wav":
            raise InvalidCanonicalAudioSettingsError("container must be wav")
        if self.codec != "pcm_s16le":
            raise InvalidCanonicalAudioSettingsError("codec must be pcm_s16le")
        if self.sample_width_bits != 16:
            raise InvalidCanonicalAudioSettingsError("sample_width_bits must be 16")
        if self.amplitude_normalization != "none":
            raise InvalidCanonicalAudioSettingsError(
                "amplitude_normalization must be none for SAX-011"
            )
        if self.schema_version != _DEFAULT_SCHEMA_VERSION:
            raise InvalidCanonicalAudioSettingsError(
                f"schema_version must be {_DEFAULT_SCHEMA_VERSION}"
            )


@dataclass(frozen=True, slots=True)
class CanonicalAudioMetadata:
    """Semantic metadata read from the converted WAV artifact."""

    container: str
    codec: str
    sample_rate_hz: int
    channels: int
    sample_width_bits: int
    duration_seconds: float
    tool_name: str
    tool_version: str
    preprocessing_schema_version: str


@dataclass(frozen=True, slots=True)
class CanonicalAudioResult:
    """Result of one canonical audio conversion."""

    original: OriginalAudioReference
    settings: CanonicalAudioSettings
    metadata: CanonicalAudioMetadata
