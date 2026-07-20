from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

NOTE_EVENT_SCHEMA_VERSION = "1.0"
NOTE_EVENT_FIELDS = (
    "pitch_concert_midi",
    "onset_seconds",
    "offset_seconds",
    "velocity",
    "confidence",
)


class InvalidNoteEventError(ValueError):
    """Raised when a note event or event batch violates the domain contract."""


class UnsupportedNoteEventSchemaVersionError(ValueError):
    """Raised when a note-event batch uses an unsupported schema version."""

    def __init__(self, schema_version: object) -> None:
        super().__init__(
            f"Unsupported note-event schema version {schema_version!r}; "
            f"expected {NOTE_EVENT_SCHEMA_VERSION!r}"
        )
        self.schema_version = schema_version


def _validate_midi_integer(*, field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidNoteEventError(f"{field_name} must be an integer between 0 and 127")
    if not 0 <= value <= 127:
        raise InvalidNoteEventError(f"{field_name} must be between 0 and 127")
    return value


def _normalize_finite_number(*, field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidNoteEventError(f"{field_name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise InvalidNoteEventError(f"{field_name} must be a finite number")
    return normalized


@dataclass(frozen=True, slots=True)
class NoteEvent:
    """Model-independent note event expressed in concert-pitch MIDI and seconds."""

    pitch_concert_midi: int
    onset_seconds: float
    offset_seconds: float
    velocity: int
    confidence: float

    def __post_init__(self) -> None:
        pitch = _validate_midi_integer(
            field_name="pitch_concert_midi",
            value=self.pitch_concert_midi,
        )
        onset = _normalize_finite_number(
            field_name="onset_seconds",
            value=self.onset_seconds,
        )
        offset = _normalize_finite_number(
            field_name="offset_seconds",
            value=self.offset_seconds,
        )
        velocity = _validate_midi_integer(field_name="velocity", value=self.velocity)
        confidence = _normalize_finite_number(
            field_name="confidence",
            value=self.confidence,
        )

        if onset < 0:
            raise InvalidNoteEventError("onset_seconds must be greater than or equal to zero")
        if offset <= onset:
            raise InvalidNoteEventError("offset_seconds must be greater than onset_seconds")
        if not 0.0 <= confidence <= 1.0:
            raise InvalidNoteEventError("confidence must be between 0.0 and 1.0")

        object.__setattr__(self, "pitch_concert_midi", pitch)
        object.__setattr__(self, "onset_seconds", onset)
        object.__setattr__(self, "offset_seconds", offset)
        object.__setattr__(self, "velocity", velocity)
        object.__setattr__(self, "confidence", confidence)

    @property
    def duration_seconds(self) -> float:
        """Return the event duration without adding a serialized field."""

        return self.offset_seconds - self.onset_seconds


@dataclass(frozen=True, slots=True)
class NoteEventBatch:
    """Ordered, versioned collection of model-independent note events."""

    events: tuple[NoteEvent, ...]
    schema_version: str = NOTE_EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != NOTE_EVENT_SCHEMA_VERSION:
            raise UnsupportedNoteEventSchemaVersionError(self.schema_version)
        normalized = self._normalize_events(self.events)
        object.__setattr__(self, "events", normalized)

    @staticmethod
    def _normalize_events(events: object) -> tuple[NoteEvent, ...]:
        if isinstance(events, (str, bytes)) or not isinstance(events, Iterable):
            raise InvalidNoteEventError("events must be an iterable of NoteEvent values")
        normalized: tuple[object, ...] = tuple(events)
        if not all(isinstance(event, NoteEvent) for event in normalized):
            raise InvalidNoteEventError("events must contain only NoteEvent values")
        return tuple(event for event in normalized if isinstance(event, NoteEvent))
