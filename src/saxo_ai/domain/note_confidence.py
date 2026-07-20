from __future__ import annotations

import math
from dataclasses import dataclass

from saxo_ai.domain.note_event_postprocessing import PostProcessedTranscriptionResult
from saxo_ai.domain.note_events import NoteEvent

LOW_CONFIDENCE_POLICY_VERSION = "1.0"
LOW_CONFIDENCE_VIEW_SCHEMA_VERSION = "1.0"
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.50
CONFIDENCE_INTERPRETATION = "model_signal_not_calibrated_accuracy"


class InvalidLowConfidenceContractError(ValueError):
    """Raised when a confidence setting, annotation, report, or result is inconsistent."""


def _low_confidence_threshold(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidLowConfidenceContractError(
            "low_confidence_threshold must be a finite number from 0.0 to 1.0"
        )
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise InvalidLowConfidenceContractError(
            "low_confidence_threshold must be a finite number from 0.0 to 1.0"
        )
    return normalized


def _non_negative_count(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidLowConfidenceContractError(f"{field_name} must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class LowConfidenceSettings:
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD
    policy_version: str = LOW_CONFIDENCE_POLICY_VERSION

    def __post_init__(self) -> None:
        threshold = _low_confidence_threshold(self.low_confidence_threshold)
        if self.policy_version != LOW_CONFIDENCE_POLICY_VERSION:
            raise InvalidLowConfidenceContractError(
                f"policy_version must be {LOW_CONFIDENCE_POLICY_VERSION!r}"
            )
        object.__setattr__(self, "low_confidence_threshold", threshold)


@dataclass(frozen=True, slots=True)
class ConfidenceAnnotatedNoteEvent:
    event: NoteEvent
    is_low_confidence: bool

    def __post_init__(self) -> None:
        if not isinstance(self.event, NoteEvent):
            raise InvalidLowConfidenceContractError("event must be a NoteEvent")
        if not isinstance(self.is_low_confidence, bool):
            raise InvalidLowConfidenceContractError("is_low_confidence must be a bool")


@dataclass(frozen=True, slots=True)
class LowConfidenceReport:
    settings: LowConfidenceSettings
    input_event_count: int
    low_confidence_count: int
    regular_confidence_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.settings, LowConfidenceSettings):
            raise InvalidLowConfidenceContractError("settings must be LowConfidenceSettings")
        for field_name in (
            "input_event_count",
            "low_confidence_count",
            "regular_confidence_count",
        ):
            _non_negative_count(field_name, getattr(self, field_name))
        if self.input_event_count != self.low_confidence_count + self.regular_confidence_count:
            raise InvalidLowConfidenceContractError(
                "input_event_count must equal low_confidence_count plus regular_confidence_count"
            )

    @property
    def affected_event_count(self) -> int:
        return self.low_confidence_count


@dataclass(frozen=True, slots=True)
class ConfidenceAnnotatedTranscriptionResult:
    original: PostProcessedTranscriptionResult
    annotated_events: tuple[ConfidenceAnnotatedNoteEvent, ...]
    report: LowConfidenceReport

    def __post_init__(self) -> None:
        if not isinstance(self.original, PostProcessedTranscriptionResult):
            raise InvalidLowConfidenceContractError(
                "original must be a PostProcessedTranscriptionResult"
            )
        if not isinstance(self.annotated_events, tuple) or not all(
            isinstance(annotation, ConfidenceAnnotatedNoteEvent)
            for annotation in self.annotated_events
        ):
            raise InvalidLowConfidenceContractError(
                "annotated_events must be a tuple of ConfidenceAnnotatedNoteEvent values"
            )
        if not isinstance(self.report, LowConfidenceReport):
            raise InvalidLowConfidenceContractError("report must be a LowConfidenceReport")
        expected_count = len(self.original.notes.events)
        if len(self.annotated_events) != expected_count:
            raise InvalidLowConfidenceContractError(
                "annotation count must equal the postprocessed note count"
            )
        if self.report.input_event_count != expected_count:
            raise InvalidLowConfidenceContractError(
                "report input_event_count must equal the postprocessed note count"
            )

        low_confidence_count = 0
        for index, annotation in enumerate(self.annotated_events):
            if annotation.event is not self.original.notes.events[index]:
                raise InvalidLowConfidenceContractError(
                    "annotations must preserve postprocessed event references and order"
                )
            if annotation.is_low_confidence:
                low_confidence_count += 1
        if low_confidence_count != self.report.low_confidence_count:
            raise InvalidLowConfidenceContractError(
                "report low_confidence_count must match annotations"
            )
