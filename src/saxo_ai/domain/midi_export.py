from __future__ import annotations

import re
from dataclasses import dataclass

from saxo_ai.domain.tempo import InvalidTempoSettingsError, normalize_positive_bpm
from saxo_ai.domain.written_pitch import (
    WrittenPitchNoteEvent,
    WrittenPitchTranscriptionResult,
)

MIDI_EXPORT_POLICY_VERSION = "1.0"
MIDI_FILE_TYPE = 1
MIDI_TICKS_PER_BEAT = 480
MIDI_CHANNEL = 0
MIDI_PITCH_REPRESENTATION = "concert"
DEFAULT_MIDI_TEMPO_BPM = 120.0
MIDI_TEMPO_MIN_MICROSECONDS_PER_BEAT = 1
MIDI_TEMPO_MAX_MICROSECONDS_PER_BEAT = 16_777_215
MIDI_MEDIA_TYPE = "audio/midi"
MIDI_FILE_EXTENSION = ".mid"
MIDI_BASE_MESSAGE_COUNT = 5
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class InvalidMidiExportSettingsError(ValueError):
    """Raised when MIDI export settings cannot be represented safely."""


class InvalidMidiPlanError(ValueError):
    """Raised when a MIDI note plan or report violates the export contract."""


class InvalidMidiArtifactError(ValueError):
    """Raised when encoded MIDI bytes or artifact metadata are inconsistent."""


def _non_negative_integer(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidMidiPlanError(f"{field_name} must be a non-negative integer")
    return value


def _positive_midi_integer(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 127:
        raise InvalidMidiPlanError(f"{field_name} must be an integer from 1 to 127")
    return value


def _tempo_microseconds_per_beat(tempo_bpm: float) -> int:
    tempo = round(60_000_000 / tempo_bpm)
    if not MIDI_TEMPO_MIN_MICROSECONDS_PER_BEAT <= tempo <= MIDI_TEMPO_MAX_MICROSECONDS_PER_BEAT:
        raise InvalidMidiExportSettingsError(
            "tempo_bpm produces an unrepresentable MIDI tempo value"
        )
    return tempo


@dataclass(frozen=True, slots=True)
class MidiExportSettings:
    tempo_bpm: float = DEFAULT_MIDI_TEMPO_BPM
    policy_version: str = MIDI_EXPORT_POLICY_VERSION

    def __post_init__(self) -> None:
        try:
            normalized = normalize_positive_bpm(self.tempo_bpm)
        except InvalidTempoSettingsError as error:
            raise InvalidMidiExportSettingsError(str(error)) from error
        if self.policy_version != MIDI_EXPORT_POLICY_VERSION:
            raise InvalidMidiExportSettingsError(
                f"policy_version must be {MIDI_EXPORT_POLICY_VERSION!r}"
            )
        _tempo_microseconds_per_beat(normalized)
        object.__setattr__(self, "tempo_bpm", normalized)

    @property
    def tempo_microseconds_per_beat(self) -> int:
        return _tempo_microseconds_per_beat(self.tempo_bpm)


@dataclass(frozen=True, slots=True)
class MidiNotePlan:
    source: WrittenPitchNoteEvent
    source_index: int
    pitch_concert_midi: int
    velocity: int
    onset_tick: int
    offset_tick: int

    def __post_init__(self) -> None:
        if not isinstance(self.source, WrittenPitchNoteEvent):
            raise InvalidMidiPlanError("source must be a WrittenPitchNoteEvent")
        source_index = _non_negative_integer("source_index", self.source_index)
        if (
            isinstance(self.pitch_concert_midi, bool)
            or not isinstance(self.pitch_concert_midi, int)
            or self.pitch_concert_midi != self.source.source.event.pitch_concert_midi
        ):
            raise InvalidMidiPlanError("pitch_concert_midi must match the source concert pitch")
        velocity = _positive_midi_integer("velocity", self.velocity)
        onset_tick = _non_negative_integer("onset_tick", self.onset_tick)
        offset_tick = _non_negative_integer("offset_tick", self.offset_tick)
        if offset_tick <= onset_tick:
            raise InvalidMidiPlanError("offset_tick must be greater than onset_tick")
        object.__setattr__(self, "source_index", source_index)
        object.__setattr__(self, "velocity", velocity)
        object.__setattr__(self, "onset_tick", onset_tick)
        object.__setattr__(self, "offset_tick", offset_tick)


@dataclass(frozen=True, slots=True)
class MidiExportReport:
    settings: MidiExportSettings
    input_event_count: int
    exported_note_count: int
    minimum_tick_adjustment_count: int
    zero_velocity_adjustment_count: int
    midi_message_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.settings, MidiExportSettings):
            raise InvalidMidiPlanError("settings must be MidiExportSettings")
        for field_name in (
            "input_event_count",
            "exported_note_count",
            "minimum_tick_adjustment_count",
            "zero_velocity_adjustment_count",
            "midi_message_count",
        ):
            _non_negative_integer(field_name, getattr(self, field_name))
        if self.input_event_count != self.exported_note_count:
            raise InvalidMidiPlanError("input_event_count must equal exported_note_count")
        if self.minimum_tick_adjustment_count > self.exported_note_count:
            raise InvalidMidiPlanError(
                "minimum_tick_adjustment_count cannot exceed exported_note_count"
            )
        if self.zero_velocity_adjustment_count > self.exported_note_count:
            raise InvalidMidiPlanError(
                "zero_velocity_adjustment_count cannot exceed exported_note_count"
            )
        expected_messages = MIDI_BASE_MESSAGE_COUNT + (2 * self.exported_note_count)
        if self.midi_message_count != expected_messages:
            raise InvalidMidiPlanError(
                "midi_message_count must include both tracks and every note message"
            )


@dataclass(frozen=True, slots=True)
class MidiArtifact:
    content: bytes
    media_type: str
    file_extension: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.content, bytes):
            raise InvalidMidiArtifactError("content must be bytes")
        if not self.content:
            raise InvalidMidiArtifactError("content must not be empty")
        if not self.content.startswith(b"MThd"):
            raise InvalidMidiArtifactError("content must begin with the Standard MIDI File header")
        if self.media_type != MIDI_MEDIA_TYPE:
            raise InvalidMidiArtifactError(f"media_type must be {MIDI_MEDIA_TYPE!r}")
        if self.file_extension != MIDI_FILE_EXTENSION:
            raise InvalidMidiArtifactError(f"file_extension must be {MIDI_FILE_EXTENSION!r}")
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes != len(self.content)
        ):
            raise InvalidMidiArtifactError("size_bytes must equal the encoded content length")
        if not isinstance(self.sha256, str) or _SHA256_PATTERN.fullmatch(self.sha256) is None:
            raise InvalidMidiArtifactError(
                "sha256 must be a lowercase 64-character hexadecimal digest"
            )


@dataclass(frozen=True, slots=True)
class MidiExportResult:
    original: WrittenPitchTranscriptionResult
    plan: tuple[MidiNotePlan, ...]
    artifact: MidiArtifact
    report: MidiExportReport

    def __post_init__(self) -> None:
        if not isinstance(self.original, WrittenPitchTranscriptionResult):
            raise InvalidMidiPlanError("original must be a WrittenPitchTranscriptionResult")
        if not isinstance(self.plan, tuple) or not all(
            isinstance(item, MidiNotePlan) for item in self.plan
        ):
            raise InvalidMidiPlanError("plan must be a tuple of MidiNotePlan values")
        if not isinstance(self.artifact, MidiArtifact):
            raise InvalidMidiArtifactError("artifact must be a MidiArtifact")
        if not isinstance(self.report, MidiExportReport):
            raise InvalidMidiPlanError("report must be a MidiExportReport")
        expected_count = len(self.original.events)
        if len(self.plan) != expected_count or self.report.exported_note_count != expected_count:
            raise InvalidMidiPlanError("plan and report counts must match the written result")
        seen_indexes: set[int] = set()
        for item in self.plan:
            if item.source_index >= expected_count:
                raise InvalidMidiPlanError("source_index must reference an original written event")
            if item.source is not self.original.events[item.source_index]:
                raise InvalidMidiPlanError("plan sources must preserve original event references")
            if item.source_index in seen_indexes:
                raise InvalidMidiPlanError("source_index values must be unique")
            seen_indexes.add(item.source_index)
        if seen_indexes != set(range(expected_count)):
            raise InvalidMidiPlanError("plan must contain every original event exactly once")
