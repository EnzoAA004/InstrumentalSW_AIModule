from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_ONSET_TOLERANCE_SECONDS = 0.05
DEFAULT_OFFSET_RATIO = 0.2
DEFAULT_OFFSET_MIN_TOLERANCE_SECONDS = 0.05


class InvalidNoteMatchToleranceError(ValueError):
    """Raised when note-matching tolerance settings violate the domain contract."""


class InvalidNoteTranscriptionMetricsError(ValueError):
    """Raised when a note-transcription metrics result violates the domain contract."""


def _require_positive_finite(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidNoteMatchToleranceError(f"{field_name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise InvalidNoteMatchToleranceError(f"{field_name} must be greater than zero")
    return normalized


@dataclass(frozen=True, slots=True)
class NoteMatchToleranceSettings:
    """Standard MIR note-transcription matching tolerances (MIREX/mir_eval defaults)."""

    onset_tolerance_seconds: float = DEFAULT_ONSET_TOLERANCE_SECONDS
    evaluate_offset: bool = False
    offset_ratio: float = DEFAULT_OFFSET_RATIO
    offset_min_tolerance_seconds: float = DEFAULT_OFFSET_MIN_TOLERANCE_SECONDS

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "onset_tolerance_seconds",
            _require_positive_finite("onset_tolerance_seconds", self.onset_tolerance_seconds),
        )
        if not isinstance(self.evaluate_offset, bool):
            raise InvalidNoteMatchToleranceError("evaluate_offset must be a boolean")
        offset_ratio = _require_positive_finite("offset_ratio", self.offset_ratio)
        if offset_ratio > 1.0:
            raise InvalidNoteMatchToleranceError("offset_ratio must be between 0 and 1")
        object.__setattr__(self, "offset_ratio", offset_ratio)
        object.__setattr__(
            self,
            "offset_min_tolerance_seconds",
            _require_positive_finite(
                "offset_min_tolerance_seconds", self.offset_min_tolerance_seconds
            ),
        )


def _require_ratio(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidNoteTranscriptionMetricsError(f"{field_name} must be a number")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise InvalidNoteTranscriptionMetricsError(f"{field_name} must be between 0.0 and 1.0")
    return normalized


def _require_non_negative_int(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidNoteTranscriptionMetricsError(f"{field_name} must be an integer")
    if value < 0:
        raise InvalidNoteTranscriptionMetricsError(f"{field_name} must not be negative")
    return value


def _require_optional_non_negative_finite(field_name: str, value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidNoteTranscriptionMetricsError(f"{field_name} must be a number or None")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise InvalidNoteTranscriptionMetricsError(
            f"{field_name} must be a non-negative finite number"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class NoteTranscriptionMetrics:
    """Note-level precision/recall/F1 and onset-timing error over matched notes."""

    tolerance: NoteMatchToleranceSettings
    reference_count: int
    estimated_count: int
    matched_count: int
    precision: float
    recall: float
    f1_score: float
    mean_onset_error_seconds: float | None
    median_onset_error_seconds: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.tolerance, NoteMatchToleranceSettings):
            raise InvalidNoteTranscriptionMetricsError(
                "tolerance must be NoteMatchToleranceSettings"
            )
        object.__setattr__(
            self,
            "reference_count",
            _require_non_negative_int("reference_count", self.reference_count),
        )
        object.__setattr__(
            self,
            "estimated_count",
            _require_non_negative_int("estimated_count", self.estimated_count),
        )
        object.__setattr__(
            self, "matched_count", _require_non_negative_int("matched_count", self.matched_count)
        )
        if self.matched_count > min(self.reference_count, self.estimated_count):
            raise InvalidNoteTranscriptionMetricsError(
                "matched_count must not exceed the smaller of reference_count and estimated_count"
            )
        object.__setattr__(self, "precision", _require_ratio("precision", self.precision))
        object.__setattr__(self, "recall", _require_ratio("recall", self.recall))
        object.__setattr__(self, "f1_score", _require_ratio("f1_score", self.f1_score))
        object.__setattr__(
            self,
            "mean_onset_error_seconds",
            _require_optional_non_negative_finite(
                "mean_onset_error_seconds", self.mean_onset_error_seconds
            ),
        )
        object.__setattr__(
            self,
            "median_onset_error_seconds",
            _require_optional_non_negative_finite(
                "median_onset_error_seconds", self.median_onset_error_seconds
            ),
        )
        if self.matched_count == 0:
            if (
                self.mean_onset_error_seconds is not None
                or self.median_onset_error_seconds is not None
            ):
                raise InvalidNoteTranscriptionMetricsError(
                    "onset error statistics must be None when no notes were matched"
                )
        elif self.mean_onset_error_seconds is None or self.median_onset_error_seconds is None:
            raise InvalidNoteTranscriptionMetricsError(
                "onset error statistics must be present when notes were matched"
            )
