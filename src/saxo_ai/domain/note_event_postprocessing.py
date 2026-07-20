from __future__ import annotations

import math
from dataclasses import dataclass

from saxo_ai.domain.note_events import NoteEventBatch
from saxo_ai.domain.transcription import TranscriptionResult

NOTE_EVENT_POSTPROCESSING_POLICY_VERSION = "1.0"
DUPLICATE_POLICY_NAME = "same_pitch_exact_interval_keep_highest_confidence"
DEFAULT_MINIMUM_DURATION_SECONDS = 0.030


class InvalidNoteEventPostProcessingContractError(ValueError):
    """Raised when a postprocessing setting, report, or result is inconsistent."""


def _minimum_duration(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidNoteEventPostProcessingContractError(
            "minimum_duration_seconds must be a finite number greater than or equal to zero"
        )
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise InvalidNoteEventPostProcessingContractError(
            "minimum_duration_seconds must be a finite number greater than or equal to zero"
        )
    return normalized


def _non_negative_count(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidNoteEventPostProcessingContractError(
            f"{field_name} must be a non-negative integer"
        )
    return value


@dataclass(frozen=True, slots=True)
class NoteEventPostProcessingSettings:
    minimum_duration_seconds: float = DEFAULT_MINIMUM_DURATION_SECONDS
    policy_version: str = NOTE_EVENT_POSTPROCESSING_POLICY_VERSION
    duplicate_policy: str = DUPLICATE_POLICY_NAME

    def __post_init__(self) -> None:
        minimum = _minimum_duration(self.minimum_duration_seconds)
        if self.policy_version != NOTE_EVENT_POSTPROCESSING_POLICY_VERSION:
            raise InvalidNoteEventPostProcessingContractError(
                f"policy_version must be {NOTE_EVENT_POSTPROCESSING_POLICY_VERSION!r}"
            )
        if self.duplicate_policy != DUPLICATE_POLICY_NAME:
            raise InvalidNoteEventPostProcessingContractError(
                f"duplicate_policy must be {DUPLICATE_POLICY_NAME!r}"
            )
        object.__setattr__(self, "minimum_duration_seconds", minimum)


@dataclass(frozen=True, slots=True)
class NoteEventPostProcessingReport:
    settings: NoteEventPostProcessingSettings
    input_event_count: int
    output_event_count: int
    short_duration_removed_count: int
    duplicate_removed_count: int
    duplicate_group_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.settings, NoteEventPostProcessingSettings):
            raise InvalidNoteEventPostProcessingContractError(
                "settings must be NoteEventPostProcessingSettings"
            )
        for field_name in (
            "input_event_count",
            "output_event_count",
            "short_duration_removed_count",
            "duplicate_removed_count",
            "duplicate_group_count",
        ):
            _non_negative_count(field_name, getattr(self, field_name))
        expected_input = (
            self.output_event_count
            + self.short_duration_removed_count
            + self.duplicate_removed_count
        )
        if self.input_event_count != expected_input:
            raise InvalidNoteEventPostProcessingContractError(
                "input_event_count must equal output_event_count plus removed counts"
            )
        if self.duplicate_removed_count == 0:
            if self.duplicate_group_count != 0:
                raise InvalidNoteEventPostProcessingContractError(
                    "duplicate_group_count must be zero when no duplicates were removed"
                )
        elif not 1 <= self.duplicate_group_count <= self.duplicate_removed_count:
            raise InvalidNoteEventPostProcessingContractError(
                "duplicate_group_count must be between one and duplicate_removed_count"
            )

    @property
    def affected_event_count(self) -> int:
        return self.short_duration_removed_count + self.duplicate_removed_count


@dataclass(frozen=True, slots=True)
class NoteEventPostProcessingResult:
    notes: NoteEventBatch
    report: NoteEventPostProcessingReport

    def __post_init__(self) -> None:
        if not isinstance(self.notes, NoteEventBatch):
            raise InvalidNoteEventPostProcessingContractError("notes must be a NoteEventBatch")
        if not isinstance(self.report, NoteEventPostProcessingReport):
            raise InvalidNoteEventPostProcessingContractError(
                "report must be a NoteEventPostProcessingReport"
            )
        if len(self.notes.events) != self.report.output_event_count:
            raise InvalidNoteEventPostProcessingContractError(
                "notes count must equal report output_event_count"
            )


@dataclass(frozen=True, slots=True)
class PostProcessedTranscriptionResult:
    original: TranscriptionResult
    notes: NoteEventBatch
    report: NoteEventPostProcessingReport

    def __post_init__(self) -> None:
        if not isinstance(self.original, TranscriptionResult):
            raise InvalidNoteEventPostProcessingContractError(
                "original must be a TranscriptionResult"
            )
        if not isinstance(self.notes, NoteEventBatch):
            raise InvalidNoteEventPostProcessingContractError("notes must be a NoteEventBatch")
        if not isinstance(self.report, NoteEventPostProcessingReport):
            raise InvalidNoteEventPostProcessingContractError(
                "report must be a NoteEventPostProcessingReport"
            )
        if len(self.original.notes.events) != self.report.input_event_count:
            raise InvalidNoteEventPostProcessingContractError(
                "original note count must equal report input_event_count"
            )
        if len(self.notes.events) != self.report.output_event_count:
            raise InvalidNoteEventPostProcessingContractError(
                "processed note count must equal report output_event_count"
            )
