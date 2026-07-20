from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import mido  # type: ignore[import-untyped]

from saxo_ai.application.midi_export import MidiEncodingError
from saxo_ai.domain.midi_export import (
    MIDI_CHANNEL,
    MIDI_FILE_TYPE,
    MIDI_TICKS_PER_BEAT,
    InvalidMidiArtifactError,
    MidiExportSettings,
    MidiNotePlan,
)

_METADATA_TRACK_NAME = "Saxo Metadata"
_CONCERT_TRACK_NAME = "Saxo Concert Pitch"
_NOTE_OFF_PRIORITY = 0
_NOTE_ON_PRIORITY = 1


@dataclass(frozen=True, slots=True)
class _AbsoluteMessage:
    absolute_tick: int
    priority: int
    source_index: int
    message_type: str
    note: int
    velocity: int


def _ordered_absolute_messages(plan: tuple[MidiNotePlan, ...]) -> tuple[_AbsoluteMessage, ...]:
    messages: list[_AbsoluteMessage] = []
    for item in plan:
        messages.extend(
            (
                _AbsoluteMessage(
                    absolute_tick=item.onset_tick,
                    priority=_NOTE_ON_PRIORITY,
                    source_index=item.source_index,
                    message_type="note_on",
                    note=item.pitch_concert_midi,
                    velocity=item.velocity,
                ),
                _AbsoluteMessage(
                    absolute_tick=item.offset_tick,
                    priority=_NOTE_OFF_PRIORITY,
                    source_index=item.source_index,
                    message_type="note_off",
                    note=item.pitch_concert_midi,
                    velocity=0,
                ),
            )
        )
    return tuple(
        sorted(
            messages,
            key=lambda item: (item.absolute_tick, item.priority, item.source_index),
        )
    )


def _append_delta_messages(track: Any, plan: tuple[MidiNotePlan, ...]) -> None:
    previous_tick = 0
    for item in _ordered_absolute_messages(plan):
        delta_tick = item.absolute_tick - previous_tick
        if delta_tick < 0:
            raise MidiEncodingError("MIDI message ordering produced a negative delta time.")
        track.append(
            mido.Message(
                item.message_type,
                note=item.note,
                velocity=item.velocity,
                channel=MIDI_CHANNEL,
                time=delta_tick,
            )
        )
        previous_tick = item.absolute_tick


def _parsed_note_messages(track: Any) -> tuple[tuple[int, str, int, int, int], ...]:
    absolute_tick = 0
    messages: list[tuple[int, str, int, int, int]] = []
    for message in track:
        if isinstance(message.time, bool) or not isinstance(message.time, int) or message.time < 0:
            raise InvalidMidiArtifactError("Parsed MIDI delta times must be non-negative integers.")
        absolute_tick += message.time
        if message.type in {"note_on", "note_off"}:
            if not 0 <= message.note <= 127 or not 0 <= message.velocity <= 127:
                raise InvalidMidiArtifactError("Parsed MIDI note data is outside the valid range.")
            messages.append(
                (absolute_tick, message.type, message.note, message.velocity, message.channel)
            )
    return tuple(messages)


def _validate_encoded_content(
    content: bytes,
    *,
    plan: tuple[MidiNotePlan, ...],
    settings: MidiExportSettings,
) -> None:
    try:
        parsed = mido.MidiFile(file=io.BytesIO(content))
    except Exception as error:
        raise InvalidMidiArtifactError("encoded content could not be parsed as MIDI") from error
    if parsed.type != MIDI_FILE_TYPE:
        raise InvalidMidiArtifactError("Encoded MIDI file type is invalid.")
    if parsed.ticks_per_beat != MIDI_TICKS_PER_BEAT:
        raise InvalidMidiArtifactError("Encoded MIDI division is invalid.")
    if len(parsed.tracks) != 2:
        raise InvalidMidiArtifactError("Encoded MIDI must contain exactly two tracks.")
    metadata_types = tuple(message.type for message in parsed.tracks[0])
    if metadata_types != ("track_name", "set_tempo", "end_of_track"):
        raise InvalidMidiArtifactError("Encoded MIDI metadata track is incomplete or out of order.")
    if parsed.tracks[0][0].name != _METADATA_TRACK_NAME:
        raise InvalidMidiArtifactError("Encoded MIDI metadata track name is invalid.")
    if parsed.tracks[0][1].tempo != settings.tempo_microseconds_per_beat:
        raise InvalidMidiArtifactError("Encoded MIDI tempo does not match export settings.")
    note_track = parsed.tracks[1]
    if not note_track or note_track[0].type != "track_name":
        raise InvalidMidiArtifactError("Encoded MIDI note track name is missing.")
    if note_track[0].name != _CONCERT_TRACK_NAME or note_track[-1].type != "end_of_track":
        raise InvalidMidiArtifactError("Encoded MIDI note track metadata is invalid.")
    parsed_messages = _parsed_note_messages(note_track)
    expected_messages = tuple(
        (
            item.absolute_tick,
            item.message_type,
            item.note,
            item.velocity,
            MIDI_CHANNEL,
        )
        for item in _ordered_absolute_messages(plan)
    )
    if parsed_messages != expected_messages:
        raise InvalidMidiArtifactError(
            "Encoded MIDI note messages do not match the validated plan."
        )
    if sum(message[1] == "note_on" for message in parsed_messages) != len(plan):
        raise InvalidMidiArtifactError("Encoded MIDI note_on count does not match the plan.")
    if sum(message[1] == "note_off" for message in parsed_messages) != len(plan):
        raise InvalidMidiArtifactError("Encoded MIDI note_off count does not match the plan.")


class MidoMidiFileEncoder:
    """Encode and externally validate a deterministic in-memory Standard MIDI File."""

    def encode(
        self,
        *,
        plan: tuple[MidiNotePlan, ...],
        settings: MidiExportSettings,
    ) -> bytes:
        try:
            midi_file = mido.MidiFile(type=MIDI_FILE_TYPE, ticks_per_beat=MIDI_TICKS_PER_BEAT)
            metadata_track = mido.MidiTrack()
            note_track = mido.MidiTrack()
            midi_file.tracks.extend((metadata_track, note_track))
            metadata_track.extend(
                (
                    mido.MetaMessage("track_name", name=_METADATA_TRACK_NAME, time=0),
                    mido.MetaMessage(
                        "set_tempo",
                        tempo=settings.tempo_microseconds_per_beat,
                        time=0,
                    ),
                    mido.MetaMessage("end_of_track", time=0),
                )
            )
            note_track.append(mido.MetaMessage("track_name", name=_CONCERT_TRACK_NAME, time=0))
            _append_delta_messages(note_track, plan)
            note_track.append(mido.MetaMessage("end_of_track", time=0))
            buffer = io.BytesIO()
            midi_file.save(file=buffer)
            content = buffer.getvalue()
            _validate_encoded_content(content, plan=plan, settings=settings)
            return content
        except (MidiEncodingError, InvalidMidiArtifactError):
            raise
        except Exception as error:
            raise MidiEncodingError(
                "Mido failed to encode the MIDI artifact."
            ) from error
