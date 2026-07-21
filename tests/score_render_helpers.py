from __future__ import annotations

import xml.etree.ElementTree as ET

from saxo_ai.application.midi_export import ExportWrittenPitchToMidi
from saxo_ai.application.musicxml_export import ExportQuantizedRhythmToMusicXml
from saxo_ai.domain.midi_export import MidiExportResult, MidiExportSettings
from saxo_ai.domain.musicxml_export import (
    MusicXmlExportResult,
    MusicXmlExportSettings,
    MusicXmlValidationSummary,
)
from saxo_ai.infrastructure.mido_midi import MidoMidiFileEncoder
from saxo_ai.infrastructure.musicxml_encoder import StandardLibraryMusicXmlEncoder
from tests.musicxml_helpers import NoteSpec, manual_quantized


class ParsingMusicXmlReader:
    def validate(self, *, content: bytes) -> MusicXmlValidationSummary:
        root = ET.fromstring(content)
        notes = root.findall("./part/measure/note")
        rest_count = sum(note.find("rest") is not None for note in notes)
        return MusicXmlValidationSummary(
            document_version=root.attrib["version"],
            part_count=len(root.findall("./part")),
            measure_count=len(root.findall("./part/measure")),
            note_segment_count=len(notes) - rest_count,
            rest_segment_count=rest_count,
            loaded_by_external_reader=True,
        )


def musicxml_result(
    specs: tuple[NoteSpec, ...] = ((60, 0.0, 0.5, 0.8, False),),
    *,
    bpm: float = 120.0,
    revision: int = 1,
    beats_per_measure: int = 4,
) -> MusicXmlExportResult:
    quantized = manual_quantized(specs, bpm=bpm, revision=revision)
    return ExportQuantizedRhythmToMusicXml(
        StandardLibraryMusicXmlEncoder(),
        ParsingMusicXmlReader(),
    ).execute(quantized, MusicXmlExportSettings(beats_per_measure))


def empty_musicxml_result(*, revision: int = 1) -> MusicXmlExportResult:
    return musicxml_result((), revision=revision)


def long_musicxml_result(*, note_count: int = 64, revision: int = 1) -> MusicXmlExportResult:
    specs = tuple(
        (
            60 + index % 12,
            index * 0.5,
            (index + 1) * 0.5,
            0.8,
            False,
        )
        for index in range(note_count)
    )
    return musicxml_result(specs, revision=revision)


def midi_result(original: MusicXmlExportResult) -> MidiExportResult:
    return ExportWrittenPitchToMidi(MidoMidiFileEncoder()).execute(
        original.original.tempo.original,
        MidiExportSettings(tempo_bpm=original.original.tempo.effective_tempo_bpm),
    )


def upstream_snapshot(
    musicxml: MusicXmlExportResult,
    midi: MidiExportResult,
) -> tuple[bytes, str, bytes, str, int, object, object]:
    return (
        midi.artifact.content,
        midi.artifact.sha256,
        musicxml.artifact.content,
        musicxml.artifact.sha256,
        musicxml.original.tempo.revision,
        musicxml.original.tempo,
        musicxml.original,
    )
