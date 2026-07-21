from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable

import pytest

from saxo_ai.application.musicxml_export import ExportQuantizedRhythmToMusicXml
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.musicxml_export import (
    MusicXmlExportResult,
    MusicXmlExportSettings,
    MusicXmlValidationSummary,
)
from saxo_ai.domain.rhythm_quantization import QuantizedRhythmResult
from saxo_ai.infrastructure.musicxml_encoder import StandardLibraryMusicXmlEncoder
from tests.musicxml_helpers import automatic_quantized, manual_quantized


class ContractReader:
    def validate(self, *, content: bytes) -> MusicXmlValidationSummary:
        root = ET.fromstring(content)
        measures = root.findall("./part/measure")
        notes = root.findall("./part/measure/note")
        rest_count = sum(note.find("rest") is not None for note in notes)
        return MusicXmlValidationSummary(
            document_version=root.attrib["version"],
            part_count=len(root.findall("./part")),
            measure_count=len(measures),
            note_segment_count=len(notes) - rest_count,
            rest_segment_count=rest_count,
            loaded_by_external_reader=True,
        )


def export(
    original: QuantizedRhythmResult,
    settings: MusicXmlExportSettings | None = None,
) -> MusicXmlExportResult:
    return ExportQuantizedRhythmToMusicXml(
        StandardLibraryMusicXmlEncoder(),
        ContractReader(),
    ).execute(original, settings or MusicXmlExportSettings())


def parse(result: MusicXmlExportResult) -> ET.Element:
    return ET.fromstring(result.artifact.content)


def duration_sum(measure: ET.Element) -> int:
    return sum(int(value.text or "0") for value in measure.findall("note/duration"))


def test_one_measure_contains_ordered_attributes_notes_rests_and_written_pitch() -> None:
    original = manual_quantized(
        (
            (60, 0.25, 0.50, 0.0, True),
            (62, 0.75, 1.00, 1.0, False),
        ),
        saxophone_type=SaxophoneType.ALTO,
    )
    result = export(original)
    root = parse(result)
    measure = root.find("./part/measure")
    assert measure is not None

    assert root.tag == "score-partwise"
    assert root.attrib == {"version": "4.0"}
    assert [child.tag for child in root] == ["work", "part-list", "part"]
    assert root.findtext("./work/work-title") == "Saxo Transcription"
    assert root.findtext("./part-list/score-part/part-name") == "Alto Saxophone in E-flat"
    assert root.findtext("./part-list/score-part/score-instrument/instrument-name") == (
        "Alto Saxophone in E-flat"
    )
    part = root.find("./part")
    assert part is not None
    assert part.attrib == {"id": "P1"}
    assert measure.attrib == {"number": "1"}
    assert [child.tag for child in measure[:2]] == ["attributes", "direction"]
    assert measure.findtext("attributes/divisions") == "4"
    assert measure.findtext("attributes/time/beats") == "4"
    assert measure.findtext("attributes/time/beat-type") == "4"
    assert measure.findtext("attributes/clef/sign") == "G"
    assert measure.findtext("attributes/clef/line") == "2"
    assert measure.findtext("attributes/transpose/diatonic") == "-5"
    assert measure.findtext("attributes/transpose/chromatic") == "-9"
    assert measure.find("attributes/transpose/octave-change") is None
    assert measure.findtext("direction/direction-type/metronome/beat-unit") == "quarter"
    assert measure.findtext("direction/direction-type/metronome/per-minute") == "120"
    sound = measure.find("direction/sound")
    assert sound is not None
    assert sound.attrib == {"tempo": "120"}

    xml_notes = measure.findall("note")
    assert len(xml_notes) == 4
    assert [note.find("rest") is not None for note in xml_notes] == [True, False, True, False]
    pitched = [note for note in xml_notes if note.find("pitch") is not None]
    assert pitched[0].findtext("pitch/step") == "A"
    assert pitched[0].find("pitch/alter") is None
    assert pitched[0].findtext("pitch/octave") == "4"
    assert pitched[0].findtext("duration") == "2"
    assert all(note.findtext("voice") == "1" for note in xml_notes)
    assert all(note.findtext("staff") == "1" for note in xml_notes)
    assert duration_sum(measure) == 8
    assert result.report.source_note_count == 2
    assert result.report.source_rest_count == 2


def test_multiple_measures_are_numbered_and_previous_measures_are_complete() -> None:
    result = export(manual_quantized(((60, 0.0, 5.0, 0.8, False),)))
    measures = parse(result).findall("./part/measure")

    assert [measure.attrib["number"] for measure in measures] == ["1", "2", "3"]
    assert [duration_sum(measure) for measure in measures] == [16, 16, 8]
    assert result.report.measure_count == 3
    assert result.report.final_measure_used_divisions == 8


def test_note_crossing_one_barline_has_start_and_stop_ties() -> None:
    result = export(manual_quantized(((60, 1.5, 2.5, 0.8, False),)))
    notes = parse(result).findall("./part/measure/note")
    pitched = [note for note in notes if note.find("pitch") is not None]

    assert len(pitched) == 2
    assert [int(note.findtext("duration", "0")) for note in pitched] == [4, 4]
    assert [note.findtext("pitch/step") for note in pitched] == ["A", "A"]
    assert [[tie.attrib["type"] for tie in note.findall("tie")] for note in pitched] == [
        ["start"],
        ["stop"],
    ]
    assert [
        [tie.attrib["type"] for tie in note.findall("notations/tied")]
        for note in pitched
    ] == [["start"], ["stop"]]
    assert result.report.source_note_count == 1
    assert result.report.note_segment_count == 2
    assert result.report.split_note_count == 1


def test_note_crossing_more_than_two_measures_has_middle_stop_and_start() -> None:
    result = export(manual_quantized(((60, 0.0, 5.0, 0.8, False),)))
    notes = [
        note
        for note in parse(result).findall("./part/measure/note")
        if note.find("pitch") is not None
    ]

    assert [int(note.findtext("duration", "0")) for note in notes] == [16, 16, 8]
    assert [[tie.attrib["type"] for tie in note.findall("tie")] for note in notes] == [
        ["start"],
        ["stop", "start"],
        ["stop"],
    ]
    assert [
        [tie.attrib["type"] for tie in note.findall("notations/tied")]
        for note in notes
    ] == [["start"], ["stop", "start"], ["stop"]]


def test_rest_crossing_barline_is_split_without_ties() -> None:
    result = export(
        manual_quantized(
            (
                (60, 0.0, 0.5, 0.8, False),
                (62, 3.0, 3.25, 0.8, False),
            )
        )
    )
    rests = [
        note
        for note in parse(result).findall("./part/measure/note")
        if note.find("rest") is not None
    ]

    assert [int(note.findtext("duration", "0")) for note in rests] == [12, 8]
    assert all(not note.findall("tie") for note in rests)
    assert all(note.find("notations") is None for note in rests)
    assert result.report.source_rest_count == 1
    assert result.report.rest_segment_count == 2
    assert result.report.split_rest_count == 1


def test_partial_last_measure_is_not_filled_with_an_invented_rest() -> None:
    result = export(manual_quantized(((60, 0.0, 0.5, 0.8, False),)))
    measure = parse(result).find("./part/measure")
    assert measure is not None

    assert duration_sum(measure) == 4
    assert len(measure.findall("note")) == 1
    assert measure.find("note/rest") is None
    assert result.report.final_measure_used_divisions == 4


def test_empty_timeline_produces_attributes_and_no_invented_duration() -> None:
    result = export(manual_quantized(()))
    root = parse(result)
    measure = root.find("./part/measure")
    assert measure is not None

    assert len(root.findall("./part/measure")) == 1
    assert measure.find("attributes") is not None
    assert measure.find("direction") is not None
    assert measure.findall("note") == []
    assert result.report.final_measure_used_divisions == 0
    assert result.validation.note_segment_count == 0
    assert result.validation.rest_segment_count == 0


@pytest.mark.parametrize(
    ("factory", "expected_source", "expected_bpm"),
    [
        (manual_quantized, "manual", "90.5"),
        (automatic_quantized, "automatic", "120"),
    ],
)
def test_tempo_direction_uses_exact_effective_resolution_without_scientific_notation(
    factory: Callable[..., QuantizedRhythmResult],
    expected_source: str,
    expected_bpm: str,
) -> None:
    bpm = 90.5 if expected_source == "manual" else 120.0
    original = factory(((60, 0.0, 0.5, 0.8, False),), bpm=bpm)
    result = export(original, MusicXmlExportSettings(beats_per_measure=3))
    measure = parse(result).find("./part/measure")
    assert measure is not None

    assert result.original is original
    assert result.original.tempo.source.value == expected_source
    assert measure.findtext("attributes/time/beats") == "3"
    assert measure.findtext("direction/direction-type/metronome/per-minute") == expected_bpm
    sound = measure.find("direction/sound")
    assert sound is not None
    assert sound.attrib["tempo"] == expected_bpm
    assert "e" not in expected_bpm.lower()
