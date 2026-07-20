from __future__ import annotations

import io
import struct
from pathlib import Path

import mido  # type: ignore[import-untyped]
import pytest

from saxo_ai.application.midi_export import ExportWrittenPitchToMidi
from saxo_ai.domain.midi_export import MidiExportSettings
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.note_confidence import (
    ConfidenceAnnotatedNoteEvent,
    ConfidenceAnnotatedTranscriptionResult,
    LowConfidenceReport,
    LowConfidenceSettings,
)
from saxo_ai.domain.note_event_postprocessing import (
    NoteEventPostProcessingReport,
    NoteEventPostProcessingSettings,
    PostProcessedTranscriptionResult,
)
from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent, WrittenPitchTranscriptionResult
from saxo_ai.infrastructure.mido_midi import MidoMidiFileEncoder

pytestmark = [pytest.mark.integration, pytest.mark.midi_integration]


def written_result(
    specs: tuple[tuple[int, float, float, int], ...],
) -> WrittenPitchTranscriptionResult:
    notes = tuple(
        NoteEvent(pitch, onset, offset, velocity, 0.8)
        for pitch, onset, offset, velocity in specs
    )
    batch = NoteEventBatch(notes)
    raw = TranscriptionResult(
        notes=batch,
        model=TranscriptionModelIdentity(
            "filosax",
            "0.1.1",
            "a" * 40,
            "model",
            "b" * 40,
            "filosax_25k.pth",
            "c" * 64,
        ),
        settings=TranscriptionSettings(16_000, "cpu", 0.3, 0.3, 0.1, "activation"),
    )
    processed = PostProcessedTranscriptionResult(
        raw,
        batch,
        NoteEventPostProcessingReport(
            NoteEventPostProcessingSettings(), len(notes), len(notes), 0, 0, 0
        ),
    )
    annotations = tuple(ConfidenceAnnotatedNoteEvent(note, False) for note in notes)
    annotated = ConfidenceAnnotatedTranscriptionResult(
        processed,
        annotations,
        LowConfidenceReport(LowConfidenceSettings(), len(notes), 0, len(notes)),
    )
    return WrittenPitchTranscriptionResult(
        annotated,
        SaxophoneType.ALTO,
        tuple(
            WrittenPitchNoteEvent(annotation, annotation.event.pitch_concert_midi + 9)
            for annotation in annotations
        ),
    )


def parse(content: bytes) -> mido.MidiFile:
    return mido.MidiFile(file=io.BytesIO(content))


def absolute_messages(
    track: mido.MidiTrack,
) -> list[tuple[int, mido.Message | mido.MetaMessage]]:
    absolute = 0
    result: list[tuple[int, mido.Message | mido.MetaMessage]] = []
    for message in track:
        absolute += message.time
        result.append((absolute, message))
    return result


def test_real_mido_encoder_produces_type_one_concert_pitch_file() -> None:
    original = written_result(((60, 0.0, 0.5, 100),))

    result = ExportWrittenPitchToMidi(MidoMidiFileEncoder()).execute(
        original, MidiExportSettings()
    )
    midi = parse(result.artifact.content)

    assert midi.type == 1
    assert midi.ticks_per_beat == 480
    assert len(midi.tracks) == 2
    assert [message.name for message in midi.tracks[0] if message.type == "track_name"] == [
        "Saxo Metadata"
    ]
    assert [message.tempo for message in midi.tracks[0] if message.type == "set_tempo"] == [
        500_000
    ]
    assert [message.name for message in midi.tracks[1] if message.type == "track_name"] == [
        "Saxo Concert Pitch"
    ]
    note_ons = [message for message in midi.tracks[1] if message.type == "note_on"]
    note_offs = [message for message in midi.tracks[1] if message.type == "note_off"]
    assert len(note_ons) == len(note_offs) == 1
    assert note_ons[0].note == 60
    assert note_ons[0].note != original.events[0].written_pitch_midi == 69
    assert note_ons[0].channel == note_offs[0].channel == 0


def test_time_conversion_delta_order_and_velocity_adjustment() -> None:
    original = written_result(
        (
            (60, 0.0, 0.5, 0),
            (62, 0.5, 1.0, 127),
        )
    )

    result = ExportWrittenPitchToMidi(MidoMidiFileEncoder()).execute(
        original, MidiExportSettings()
    )
    events = absolute_messages(parse(result.artifact.content).tracks[1])
    notes = [
        (tick, message)
        for tick, message in events
        if message.type in {"note_on", "note_off"}
    ]

    assert [(tick, message.type, message.note) for tick, message in notes] == [
        (0, "note_on", 60),
        (480, "note_off", 60),
        (480, "note_on", 62),
        (960, "note_off", 62),
    ]
    assert [message.velocity for _, message in notes if message.type == "note_on"] == [1, 127]
    assert all(message.time >= 0 for message in parse(result.artifact.content).tracks[1])
    assert result.report.zero_velocity_adjustment_count == 1


def test_overlaps_are_preserved_as_independent_note_pairs() -> None:
    original = written_result(
        (
            (60, 0.0, 1.0, 100),
            (60, 0.5, 1.5, 90),
        )
    )

    result = ExportWrittenPitchToMidi(MidoMidiFileEncoder()).execute(
        original, MidiExportSettings()
    )
    track = parse(result.artifact.content).tracks[1]

    assert sum(message.type == "note_on" for message in track) == 2
    assert sum(message.type == "note_off" for message in track) == 2
    assert result.report.exported_note_count == 2


def test_empty_batch_is_still_valid_midi() -> None:
    result = ExportWrittenPitchToMidi(MidoMidiFileEncoder()).execute(
        written_result(()), MidiExportSettings()
    )
    midi = parse(result.artifact.content)

    assert result.artifact.content.startswith(b"MThd")
    assert len(midi.tracks) == 2
    assert sum(message.type == "note_on" for message in midi.tracks[1]) == 0
    assert sum(message.type == "note_off" for message in midi.tracks[1]) == 0
    assert any(message.type == "set_tempo" for message in midi.tracks[0])


def test_standard_library_structural_snapshot() -> None:
    content = ExportWrittenPitchToMidi(MidoMidiFileEncoder()).execute(
        written_result(((60, 0.0, 0.5, 100),)), MidiExportSettings()
    ).artifact.content

    assert content[:4] == b"MThd"
    header_length = struct.unpack(">I", content[4:8])[0]
    file_type, track_count, division = struct.unpack(">HHH", content[8:14])
    assert header_length == 6
    assert file_type == 1
    assert track_count == 2
    assert division == 480

    position = 8 + header_length
    chunks: list[bytes] = []
    while position < len(content):
        chunk_type = content[position : position + 4]
        chunk_length = struct.unpack(">I", content[position + 4 : position + 8])[0]
        chunks.append(chunk_type)
        position += 8 + chunk_length
    assert chunks == [b"MTrk", b"MTrk"]
    assert position == len(content)


def test_artifact_can_be_opened_from_temporary_file(tmp_path: Path) -> None:
    result = ExportWrittenPitchToMidi(MidoMidiFileEncoder()).execute(
        written_result(((60, 0.0, 0.5, 100),)), MidiExportSettings()
    )
    path = tmp_path / "transcription.mid"
    path.write_bytes(result.artifact.content)

    midi = mido.MidiFile(path)

    assert midi.type == 1
    assert len(midi.tracks) == 2
    assert path.read_bytes() == result.artifact.content


def test_real_encoder_is_deterministic_and_tempo_sensitive() -> None:
    original = written_result(((60, 0.0, 0.5, 100),))
    use_case = ExportWrittenPitchToMidi(MidoMidiFileEncoder())

    first = use_case.execute(original, MidiExportSettings(tempo_bpm=120))
    second = use_case.execute(original, MidiExportSettings(tempo_bpm=120))
    slow = use_case.execute(original, MidiExportSettings(tempo_bpm=60))

    assert first.artifact.content == second.artifact.content
    assert first.artifact.sha256 == second.artifact.sha256
    assert first.artifact.sha256 != slow.artifact.sha256
    assert [
        message.note
        for message in parse(first.artifact.content).tracks[1]
        if message.type == "note_on"
    ] == [60]
    assert [
        message.note
        for message in parse(slow.artifact.content).tracks[1]
        if message.type == "note_on"
    ] == [60]
    assert [
        message.tempo
        for message in parse(first.artifact.content).tracks[0]
        if message.type == "set_tempo"
    ] == [500_000]
    assert [
        message.tempo
        for message in parse(slow.artifact.content).tracks[0]
        if message.type == "set_tempo"
    ] == [1_000_000]
    assert first.plan[0].offset_tick == 480
    assert slow.plan[0].offset_tick == 240
