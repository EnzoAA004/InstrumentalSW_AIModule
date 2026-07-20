from __future__ import annotations

from dataclasses import dataclass

from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.note_confidence import (
    ConfidenceAnnotatedNoteEvent,
    ConfidenceAnnotatedTranscriptionResult,
)
from saxo_ai.domain.transposition import transpose_concert_pitch, written_pitch_offset_for

WRITTEN_PITCH_POLICY_VERSION = "1.0"


class InvalidWrittenPitchContractError(ValueError):
    """Raised when a written-pitch event or result violates its contract."""


def _validate_written_pitch(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidWrittenPitchContractError(
            "written_pitch_midi must be an integer between 0 and 127"
        )
    if not 0 <= value <= 127:
        raise InvalidWrittenPitchContractError("written_pitch_midi must be between 0 and 127")
    return value


@dataclass(frozen=True, slots=True)
class WrittenPitchNoteEvent:
    source: ConfidenceAnnotatedNoteEvent
    written_pitch_midi: int

    def __post_init__(self) -> None:
        if not isinstance(self.source, ConfidenceAnnotatedNoteEvent):
            raise InvalidWrittenPitchContractError("source must be a ConfidenceAnnotatedNoteEvent")
        written_pitch = _validate_written_pitch(self.written_pitch_midi)
        object.__setattr__(self, "written_pitch_midi", written_pitch)


@dataclass(frozen=True, slots=True)
class WrittenPitchTranscriptionResult:
    original: ConfidenceAnnotatedTranscriptionResult
    saxophone_type: SaxophoneType
    events: tuple[WrittenPitchNoteEvent, ...]
    policy_version: str = WRITTEN_PITCH_POLICY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.original, ConfidenceAnnotatedTranscriptionResult):
            raise InvalidWrittenPitchContractError(
                "original must be a ConfidenceAnnotatedTranscriptionResult"
            )
        written_pitch_offset_for(self.saxophone_type)
        if not isinstance(self.events, tuple) or not all(
            isinstance(event, WrittenPitchNoteEvent) for event in self.events
        ):
            raise InvalidWrittenPitchContractError(
                "events must be a tuple of WrittenPitchNoteEvent values"
            )
        if self.policy_version != WRITTEN_PITCH_POLICY_VERSION:
            raise InvalidWrittenPitchContractError(
                f"policy_version must be {WRITTEN_PITCH_POLICY_VERSION!r}"
            )
        if len(self.events) != len(self.original.annotated_events):
            raise InvalidWrittenPitchContractError(
                "written event count must equal annotated event count"
            )

        for index, written_event in enumerate(self.events):
            source = self.original.annotated_events[index]
            if written_event.source is not source:
                raise InvalidWrittenPitchContractError(
                    "written events must preserve annotation references and order"
                )
            expected = transpose_concert_pitch(
                source.event.pitch_concert_midi,
                self.saxophone_type,
            )
            if written_event.written_pitch_midi != expected:
                raise InvalidWrittenPitchContractError(
                    "written_pitch_midi must equal concert pitch plus saxophone offset"
                )
