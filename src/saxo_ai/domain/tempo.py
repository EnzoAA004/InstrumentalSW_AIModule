from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult

TEMPO_POLICY_VERSION = "1.0"
TEMPO_ESTIMATOR_NAME = "median_onset_interval"
TEMPO_ESTIMATOR_VERSION = "1.0"
DEFAULT_MINIMUM_BPM = 40.0
DEFAULT_MAXIMUM_BPM = 240.0
DEFAULT_MINIMUM_INTERVAL_COUNT = 2
DEFAULT_CONSENSUS_TOLERANCE = 0.08
TEMPO_CONFIDENCE_METHOD = "octave_equivalent_ioi_consensus_ratio"


class InvalidTempoSettingsError(ValueError):
    """Raised when tempo settings or a manual BPM value are invalid."""


class InvalidTempoEstimateError(ValueError):
    """Raised when an automatic estimate violates its immutable contract."""


class TempoEstimationUnavailableError(ValueError):
    """Raised when note onsets cannot support the configured tempo estimate."""

    def __init__(
        self,
        message: str,
        *,
        unique_onset_count: int,
        interval_count: int,
        minimum_interval_count: int,
    ) -> None:
        super().__init__(message)
        self.unique_onset_count = unique_onset_count
        self.interval_count = interval_count
        self.minimum_interval_count = minimum_interval_count


class InvalidTempoResolutionError(ValueError):
    """Raised when a selected tempo and its revision metadata are inconsistent."""


def normalize_positive_bpm(value: object, *, field_name: str = "tempo_bpm") -> float:
    """Normalize a finite positive BPM value without applying policy bounds."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTempoSettingsError(f"{field_name} must be a finite number greater than zero")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise InvalidTempoSettingsError(f"{field_name} must be a finite number greater than zero")
    return normalized


def normalize_unit_interval(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTempoSettingsError(f"{field_name} must be a finite number from 0.0 to 1.0")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise InvalidTempoSettingsError(f"{field_name} must be a finite number from 0.0 to 1.0")
    return normalized


def _non_negative_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidTempoEstimateError(f"{field_name} must be a non-negative integer")
    return value


def _non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidTempoEstimateError(f"{field_name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class TempoEstimationSettings:
    minimum_bpm: float = DEFAULT_MINIMUM_BPM
    maximum_bpm: float = DEFAULT_MAXIMUM_BPM
    minimum_interval_count: int = DEFAULT_MINIMUM_INTERVAL_COUNT
    consensus_tolerance: float = DEFAULT_CONSENSUS_TOLERANCE
    policy_version: str = TEMPO_POLICY_VERSION

    def __post_init__(self) -> None:
        minimum = normalize_positive_bpm(self.minimum_bpm, field_name="minimum_bpm")
        maximum = normalize_positive_bpm(self.maximum_bpm, field_name="maximum_bpm")
        if minimum >= maximum:
            raise InvalidTempoSettingsError("minimum_bpm must be less than maximum_bpm")
        if (
            isinstance(self.minimum_interval_count, bool)
            or not isinstance(self.minimum_interval_count, int)
            or self.minimum_interval_count <= 0
        ):
            raise InvalidTempoSettingsError("minimum_interval_count must be a positive integer")
        tolerance = normalize_unit_interval(
            self.consensus_tolerance,
            field_name="consensus_tolerance",
        )
        if self.policy_version != TEMPO_POLICY_VERSION:
            raise InvalidTempoSettingsError(
                f"policy_version must be {TEMPO_POLICY_VERSION!r}"
            )
        object.__setattr__(self, "minimum_bpm", minimum)
        object.__setattr__(self, "maximum_bpm", maximum)
        object.__setattr__(self, "consensus_tolerance", tolerance)


@dataclass(frozen=True, slots=True)
class AutomaticTempoEstimate:
    tempo_bpm: float
    confidence: float
    estimator_name: str
    estimator_version: str
    confidence_method: str
    unique_onset_count: int
    interval_count: int
    inlier_interval_count: int

    def __post_init__(self) -> None:
        try:
            tempo = normalize_positive_bpm(self.tempo_bpm)
        except InvalidTempoSettingsError as error:
            raise InvalidTempoEstimateError(str(error)) from error
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise InvalidTempoEstimateError("confidence must be a finite number from 0.0 to 1.0")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise InvalidTempoEstimateError("confidence must be a finite number from 0.0 to 1.0")
        _non_empty_string(self.estimator_name, field_name="estimator_name")
        _non_empty_string(self.estimator_version, field_name="estimator_version")
        _non_empty_string(self.confidence_method, field_name="confidence_method")
        unique_count = _non_negative_integer(
            self.unique_onset_count,
            field_name="unique_onset_count",
        )
        interval_count = _non_negative_integer(
            self.interval_count,
            field_name="interval_count",
        )
        inlier_count = _non_negative_integer(
            self.inlier_interval_count,
            field_name="inlier_interval_count",
        )
        if interval_count != unique_count - 1:
            raise InvalidTempoEstimateError(
                "interval_count must equal unique_onset_count minus one"
            )
        if inlier_count > interval_count:
            raise InvalidTempoEstimateError(
                "inlier_interval_count cannot exceed interval_count"
            )
        expected_confidence = inlier_count / interval_count if interval_count else 0.0
        if not math.isclose(confidence, expected_confidence, rel_tol=0.0, abs_tol=1e-12):
            raise InvalidTempoEstimateError(
                "confidence must equal inlier_interval_count divided by interval_count"
            )
        object.__setattr__(self, "tempo_bpm", tempo)
        object.__setattr__(self, "confidence", confidence)


class TempoSelectionSource(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class TempoResolution:
    original: WrittenPitchTranscriptionResult
    automatic_estimate: AutomaticTempoEstimate | None
    manual_tempo_bpm: float | None
    effective_tempo_bpm: float
    source: TempoSelectionSource
    revision: int
    policy_version: str = TEMPO_POLICY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.original, WrittenPitchTranscriptionResult):
            raise InvalidTempoResolutionError(
                "original must be a WrittenPitchTranscriptionResult"
            )
        if self.automatic_estimate is not None and not isinstance(
            self.automatic_estimate,
            AutomaticTempoEstimate,
        ):
            raise InvalidTempoResolutionError(
                "automatic_estimate must be AutomaticTempoEstimate or None"
            )
        try:
            effective = normalize_positive_bpm(self.effective_tempo_bpm)
            manual = (
                None
                if self.manual_tempo_bpm is None
                else normalize_positive_bpm(self.manual_tempo_bpm, field_name="manual_tempo_bpm")
            )
        except InvalidTempoSettingsError as error:
            raise InvalidTempoResolutionError(str(error)) from error
        if not isinstance(self.source, TempoSelectionSource):
            raise InvalidTempoResolutionError("source must be TempoSelectionSource")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise InvalidTempoResolutionError("revision must be a positive integer")
        if self.policy_version != TEMPO_POLICY_VERSION:
            raise InvalidTempoResolutionError(
                f"policy_version must be {TEMPO_POLICY_VERSION!r}"
            )
        if self.source is TempoSelectionSource.AUTOMATIC:
            if self.automatic_estimate is None:
                raise InvalidTempoResolutionError(
                    "automatic source requires an automatic_estimate"
                )
            if manual is not None:
                raise InvalidTempoResolutionError(
                    "automatic source cannot include manual_tempo_bpm"
                )
            if effective != self.automatic_estimate.tempo_bpm:
                raise InvalidTempoResolutionError(
                    "effective_tempo_bpm must equal the automatic estimate"
                )
            if self.revision != 1:
                raise InvalidTempoResolutionError(
                    "automatic source must start at revision one"
                )
        else:
            if manual is None:
                raise InvalidTempoResolutionError(
                    "manual source requires manual_tempo_bpm"
                )
            if effective != manual:
                raise InvalidTempoResolutionError(
                    "effective_tempo_bpm must equal manual_tempo_bpm"
                )
        object.__setattr__(self, "manual_tempo_bpm", manual)
        object.__setattr__(self, "effective_tempo_bpm", effective)
