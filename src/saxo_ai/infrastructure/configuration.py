from __future__ import annotations

import math
import os
from collections.abc import Mapping

from saxo_ai.domain.audio import AudioProcessingLimits

MAX_SIZE_ENV = "SAXO_MAX_AUDIO_SIZE_BYTES"
MAX_DURATION_ENV = "SAXO_MAX_AUDIO_DURATION_SECONDS"


class AudioProcessingConfigurationError(ValueError):
    """Raised when runtime audio-limit configuration cannot be parsed or validated."""


def load_audio_processing_limits(
    environ: Mapping[str, str] | None = None,
) -> AudioProcessingLimits:
    values = os.environ if environ is None else environ
    defaults = AudioProcessingLimits()

    size = _load_size(values.get(MAX_SIZE_ENV), defaults.max_size_bytes)
    duration = _load_duration(values.get(MAX_DURATION_ENV), defaults.max_duration_seconds)
    return AudioProcessingLimits(
        max_size_bytes=size,
        max_duration_seconds=duration,
    )


def _load_size(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw, 10)
    except ValueError as error:
        raise AudioProcessingConfigurationError(
            f"{MAX_SIZE_ENV} must be a positive integer"
        ) from error
    if value <= 0:
        raise AudioProcessingConfigurationError(f"{MAX_SIZE_ENV} must be a positive integer")
    return value


def _load_duration(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as error:
        raise AudioProcessingConfigurationError(
            f"{MAX_DURATION_ENV} must be a finite positive number"
        ) from error
    if not math.isfinite(value) or value <= 0:
        raise AudioProcessingConfigurationError(
            f"{MAX_DURATION_ENV} must be a finite positive number"
        )
    return value
