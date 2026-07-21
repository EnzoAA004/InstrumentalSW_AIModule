from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from typing import TypeVar

from saxo_ai.domain.tempo import TempoResolution
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent

RHYTHM_QUANTIZATION_POLICY_VERSION = "1.0"
DEFAULT_SUBDIVISIONS_PER_BEAT = 4
QUANTIZATION_ROUNDING_MODE = "nearest_half_up"
OVERLAP_POLICY = "truncate_earlier_then_shift_same_step"
REST_POLICY = "explicit_positive_grid_gaps"


class InvalidRhythmQuantizationSettingsError(ValueError):
    """Raised when rhythm-grid settings violate their immutable contract."""


class InvalidQuantizedNoteError(ValueError):
    """Raised when one quantized note violates its immutable contract."""


class InvalidQuantizedRestError(ValueError):
    """Raised when one explicit rest violates its immutable contract."""


class InvalidRhythmQuantizationReportError(ValueError):
    """Raised when rhythm-quantization counters or metrics are inconsistent."""


class InvalidQuantizedRhythmResultError(ValueError):
    """Raised when a quantized monophonic timeline violates its contract."""


_ErrorT = TypeVar("_ErrorT", bound=ValueError)


def _non_negative_integer(
    value: object,
    *,
    field_name: str,
    error_type: type[_ErrorT],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise error_type(f"{field_name} must be a non-negative integer")
    return value


def _finite_float(
    value: object,
    *,
    field_name: str,
    error_type: type[_ErrorT],
    non_negative: bool,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        qualifier = "non-negative " if non_negative else ""
        raise error_type(f"{field_name} must be a finite {qualifier}number")
    normalized = float(value)
    if not math.isfinite(normalized) or (non_negative and normalized < 0.0):
        qualifier = "non-negative " if non_negative else ""
        raise error_type(f"{field_name} must be a finite {qualifier}number")
    return normalized


@dataclass(frozen=True, slots=True)
class RhythmQuantizationSettings:
    subdivisions_per_beat: int = DEFAULT_SUBDIVISIONS_PER_BEAT
    policy_version: str = RHYTHM_QUANTIZATION_POLICY_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.subdivisions_per_beat, bool)
            or not isinstance(self.subdivisions_per_beat, int)
            or self.subdivisions_per_beat <= 0
        ):
            raise InvalidRhythmQuantizationSettingsError(
                "subdivisions_per_beat must be a positive integer"
            )
        if self.policy_version != RHYTHM_QUANTIZATION_POLICY_VERSION:
            raise InvalidRhythmQuantizationSettingsError(
                f"policy_version must be {RHYTHM_QUANTIZATION_POLICY_VERSION!r}"
            )


@dataclass(frozen=True, slots=True)
class QuantizedNoteEvent:
    source: WrittenPitchNoteEvent
    source_index: int
    quantized_onset_step: int
    quantized_offset_step: int
    onset_delta_seconds: float
    offset_delta_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.source, WrittenPitchNoteEvent):
            raise InvalidQuantizedNoteError("source must be a WrittenPitchNoteEvent")
        source_index = _non_negative_integer(
            self.source_index,
            field_name="source_index",
            error_type=InvalidQuantizedNoteError,
        )
        onset = _non_negative_integer(
            self.quantized_onset_step,
            field_name="quantized_onset_step",
            error_type=InvalidQuantizedNoteError,
        )
        offset = _non_negative_integer(
            self.quantized_offset_step,
            field_name="quantized_offset_step",
            error_type=InvalidQuantizedNoteError,
        )
        if offset <= onset:
            raise InvalidQuantizedNoteError(
                "quantized_offset_step must be greater than quantized_onset_step"
            )
        onset_delta = _finite_float(
            self.onset_delta_seconds,
            field_name="onset_delta_seconds",
            error_type=InvalidQuantizedNoteError,
            non_negative=False,
        )
        offset_delta = _finite_float(
            self.offset_delta_seconds,
            field_name="offset_delta_seconds",
            error_type=InvalidQuantizedNoteError,
            non_negative=False,
        )
        object.__setattr__(self, "source_index", source_index)
        object.__setattr__(self, "quantized_onset_step", onset)
        object.__setattr__(self, "quantized_offset_step", offset)
        object.__setattr__(self, "onset_delta_seconds", onset_delta)
        object.__setattr__(self, "offset_delta_seconds", offset_delta)

    @property
    def duration_steps(self) -> int:
        return self.quantized_offset_step - self.quantized_onset_step


@dataclass(frozen=True, slots=True)
class QuantizedRest:
    onset_step: int
    offset_step: int

    def __post_init__(self) -> None:
        onset = _non_negative_integer(
            self.onset_step,
            field_name="onset_step",
            error_type=InvalidQuantizedRestError,
        )
        offset = _non_negative_integer(
            self.offset_step,
            field_name="offset_step",
            error_type=InvalidQuantizedRestError,
        )
        if offset <= onset:
            raise InvalidQuantizedRestError("offset_step must be greater than onset_step")
        object.__setattr__(self, "onset_step", onset)
        object.__setattr__(self, "offset_step", offset)

    @property
    def duration_steps(self) -> int:
        return self.offset_step - self.onset_step


QuantizedTimelineItem = QuantizedNoteEvent | QuantizedRest


@dataclass(frozen=True, slots=True)
class RhythmQuantizationReport:
    settings: RhythmQuantizationSettings
    input_event_count: int
    quantized_note_count: int
    rest_count: int
    minimum_duration_adjustment_count: int
    overlap_adjusted_event_count: int
    total_absolute_onset_delta_seconds: float
    total_absolute_offset_delta_seconds: float
    maximum_absolute_boundary_delta_seconds: float

    def __post_init__(self) -> None:
        if not isinstance(self.settings, RhythmQuantizationSettings):
            raise InvalidRhythmQuantizationReportError(
                "settings must be RhythmQuantizationSettings"
            )
        count_fields = (
            "input_event_count",
            "quantized_note_count",
            "rest_count",
            "minimum_duration_adjustment_count",
            "overlap_adjusted_event_count",
        )
        counts = {
            field_name: _non_negative_integer(
                getattr(self, field_name),
                field_name=field_name,
                error_type=InvalidRhythmQuantizationReportError,
            )
            for field_name in count_fields
        }
        if counts["input_event_count"] != counts["quantized_note_count"]:
            raise InvalidRhythmQuantizationReportError(
                "input_event_count must equal quantized_note_count"
            )
        if counts["minimum_duration_adjustment_count"] > counts["quantized_note_count"]:
            raise InvalidRhythmQuantizationReportError(
                "minimum_duration_adjustment_count cannot exceed quantized_note_count"
            )
        if counts["overlap_adjusted_event_count"] > counts["quantized_note_count"]:
            raise InvalidRhythmQuantizationReportError(
                "overlap_adjusted_event_count cannot exceed quantized_note_count"
            )
        metric_fields = (
            "total_absolute_onset_delta_seconds",
            "total_absolute_offset_delta_seconds",
            "maximum_absolute_boundary_delta_seconds",
        )
        for field_name in metric_fields:
            normalized = _finite_float(
                getattr(self, field_name),
                field_name=field_name,
                error_type=InvalidRhythmQuantizationReportError,
                non_negative=True,
            )
            object.__setattr__(self, field_name, normalized)

    @property
    def total_absolute_timing_delta_seconds(self) -> float:
        return self.total_absolute_onset_delta_seconds + self.total_absolute_offset_delta_seconds

    @property
    def mean_absolute_boundary_delta_seconds(self) -> float:
        boundary_count = self.quantized_note_count * 2
        if boundary_count == 0:
            return 0.0
        return self.total_absolute_timing_delta_seconds / boundary_count


def _timeline_bounds(item: QuantizedTimelineItem) -> tuple[int, int]:
    if isinstance(item, QuantizedNoteEvent):
        return item.quantized_onset_step, item.quantized_offset_step
    return item.onset_step, item.offset_step


@dataclass(frozen=True, slots=True)
class QuantizedRhythmResult:
    tempo: TempoResolution
    timeline: tuple[QuantizedTimelineItem, ...]
    report: RhythmQuantizationReport

    def __post_init__(self) -> None:
        if not isinstance(self.tempo, TempoResolution):
            raise InvalidQuantizedRhythmResultError("tempo must be a TempoResolution")
        if not isinstance(self.timeline, tuple) or not all(
            isinstance(item, (QuantizedNoteEvent, QuantizedRest)) for item in self.timeline
        ):
            raise InvalidQuantizedRhythmResultError(
                "timeline must be a tuple of quantized notes and rests"
            )
        if not isinstance(self.report, RhythmQuantizationReport):
            raise InvalidQuantizedRhythmResultError("report must be a RhythmQuantizationReport")

        notes = tuple(item for item in self.timeline if isinstance(item, QuantizedNoteEvent))
        rests = tuple(item for item in self.timeline if isinstance(item, QuantizedRest))
        original_events = self.tempo.original.events

        if self.report.settings.policy_version != RHYTHM_QUANTIZATION_POLICY_VERSION:
            raise InvalidQuantizedRhythmResultError(
                "report settings must use the current rhythm policy"
            )
        if self.report.input_event_count != len(original_events):
            raise InvalidQuantizedRhythmResultError(
                "report input count must match the tempo original"
            )
        if self.report.quantized_note_count != len(notes):
            raise InvalidQuantizedRhythmResultError("report note count must match the timeline")
        if self.report.rest_count != len(rests):
            raise InvalidQuantizedRhythmResultError("report rest count must match the timeline")

        indexes = tuple(note.source_index for note in notes)
        if len(set(indexes)) != len(indexes) or set(indexes) != set(range(len(original_events))):
            raise InvalidQuantizedRhythmResultError(
                "every original source index must appear exactly once"
            )
        for note in notes:
            if note.source is not original_events[note.source_index]:
                raise InvalidQuantizedRhythmResultError(
                    "quantized notes must preserve exact source references"
                )

        if self.timeline:
            first_onset, _ = _timeline_bounds(self.timeline[0])
            if first_onset != 0:
                raise InvalidQuantizedRhythmResultError(
                    "a non-empty timeline must begin at step zero"
                )
            if isinstance(self.timeline[-1], QuantizedRest):
                raise InvalidQuantizedRhythmResultError("a timeline cannot invent a final rest")
            for previous, current in pairwise(self.timeline):
                _, previous_offset = _timeline_bounds(previous)
                current_onset, _ = _timeline_bounds(current)
                if previous_offset != current_onset:
                    raise InvalidQuantizedRhythmResultError(
                        "timeline items must be contiguous and non-overlapping"
                    )
                if isinstance(previous, QuantizedRest) and isinstance(current, QuantizedRest):
                    raise InvalidQuantizedRhythmResultError(
                        "timeline cannot contain consecutive rests"
                    )

        expected_onset_total = math.fsum(abs(note.onset_delta_seconds) for note in notes)
        expected_offset_total = math.fsum(abs(note.offset_delta_seconds) for note in notes)
        expected_maximum = max(
            (
                abs(delta)
                for note in notes
                for delta in (
                    note.onset_delta_seconds,
                    note.offset_delta_seconds,
                )
            ),
            default=0.0,
        )
        expected_metrics = (
            (
                self.report.total_absolute_onset_delta_seconds,
                expected_onset_total,
                "total_absolute_onset_delta_seconds",
            ),
            (
                self.report.total_absolute_offset_delta_seconds,
                expected_offset_total,
                "total_absolute_offset_delta_seconds",
            ),
            (
                self.report.maximum_absolute_boundary_delta_seconds,
                expected_maximum,
                "maximum_absolute_boundary_delta_seconds",
            ),
        )
        for actual, expected, field_name in expected_metrics:
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
                raise InvalidQuantizedRhythmResultError(
                    f"{field_name} must be calculated from quantized note deltas"
                )
