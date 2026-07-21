from __future__ import annotations

import math
from hashlib import sha256
from typing import Protocol, runtime_checkable

from saxo_ai.domain.midi_export import (
    MIDI_BASE_MESSAGE_COUNT,
    MIDI_FILE_EXTENSION,
    MIDI_MEDIA_TYPE,
    MIDI_TICKS_PER_BEAT,
    InvalidMidiArtifactError,
    InvalidMidiExportSettingsError,
    InvalidMidiPlanError,
    MidiArtifact,
    MidiExportReport,
    MidiExportResult,
    MidiExportSettings,
    MidiNotePlan,
)
from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult


class MidiEncodingError(RuntimeError):
    """Raised when an external MIDI encoder fails unexpectedly."""


@runtime_checkable
class MidiFileEncoder(Protocol):
    def encode(
        self,
        *,
        plan: tuple[MidiNotePlan, ...],
        settings: MidiExportSettings,
    ) -> bytes: ...


def seconds_to_midi_tick(seconds: float, settings: MidiExportSettings) -> int:
    """Convert non-negative seconds to a rounded absolute MIDI tick."""

    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise InvalidMidiPlanError("seconds must be a finite non-negative number")
    normalized = float(seconds)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise InvalidMidiPlanError("seconds must be a finite non-negative number")
    if not isinstance(settings, MidiExportSettings):
        raise InvalidMidiExportSettingsError("settings must be MidiExportSettings")
    converted = normalized * MIDI_TICKS_PER_BEAT * 1_000_000 / settings.tempo_microseconds_per_beat
    return max(0, round(converted))


def build_midi_artifact(content: bytes) -> MidiArtifact:
    """Build immutable artifact metadata from validated in-memory MIDI bytes."""

    if not isinstance(content, bytes):
        raise InvalidMidiArtifactError("encoder output must be bytes")
    return MidiArtifact(
        content=content,
        media_type=MIDI_MEDIA_TYPE,
        file_extension=MIDI_FILE_EXTENSION,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
    )


def _plan_sort_key(item: MidiNotePlan) -> tuple[int, int, int, int]:
    return (
        item.onset_tick,
        item.offset_tick,
        item.pitch_concert_midi,
        item.source_index,
    )


class ExportWrittenPitchToMidi:
    def __init__(self, encoder: MidiFileEncoder) -> None:
        if not isinstance(encoder, MidiFileEncoder):
            raise TypeError("encoder must implement MidiFileEncoder")
        self._encoder = encoder

    def execute(
        self,
        original: WrittenPitchTranscriptionResult,
        settings: MidiExportSettings,
    ) -> MidiExportResult:
        if not isinstance(original, WrittenPitchTranscriptionResult):
            raise InvalidMidiPlanError("original must be a WrittenPitchTranscriptionResult")
        if not isinstance(settings, MidiExportSettings):
            raise InvalidMidiExportSettingsError("settings must be MidiExportSettings")

        plan_items: list[MidiNotePlan] = []
        minimum_tick_adjustment_count = 0
        zero_velocity_adjustment_count = 0
        for source_index, source in enumerate(original.events):
            event = source.source.event
            onset_tick = seconds_to_midi_tick(event.onset_seconds, settings)
            raw_offset_tick = seconds_to_midi_tick(event.offset_seconds, settings)
            offset_tick = max(onset_tick + 1, raw_offset_tick)
            if offset_tick != raw_offset_tick:
                minimum_tick_adjustment_count += 1
            velocity = event.velocity
            if velocity == 0:
                velocity = 1
                zero_velocity_adjustment_count += 1
            plan_items.append(
                MidiNotePlan(
                    source=source,
                    source_index=source_index,
                    pitch_concert_midi=event.pitch_concert_midi,
                    velocity=velocity,
                    onset_tick=onset_tick,
                    offset_tick=offset_tick,
                )
            )

        plan = tuple(sorted(plan_items, key=_plan_sort_key))
        try:
            content = self._encoder.encode(plan=plan, settings=settings)
        except (MidiEncodingError, InvalidMidiArtifactError):
            raise
        except Exception as error:
            raise MidiEncodingError("MIDI encoding failed.") from error
        artifact = build_midi_artifact(content)
        report = MidiExportReport(
            settings=settings,
            input_event_count=len(original.events),
            exported_note_count=len(plan),
            minimum_tick_adjustment_count=minimum_tick_adjustment_count,
            zero_velocity_adjustment_count=zero_velocity_adjustment_count,
            midi_message_count=MIDI_BASE_MESSAGE_COUNT + (2 * len(plan)),
        )
        return MidiExportResult(
            original=original,
            plan=plan,
            artifact=artifact,
            report=report,
        )
