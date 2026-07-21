from __future__ import annotations

from decimal import Decimal
from xml.etree import ElementTree as ET

from saxo_ai.application.musicxml_export import (
    MusicXmlSegment,
    musicxml_pitch_for_midi,
    plan_musicxml_score,
)
from saxo_ai.domain.musicxml_export import (
    MUSICXML_BEAT_TYPE,
    MUSICXML_DOCUMENT_VERSION,
    MUSICXML_SCORE_TYPE,
    MusicXmlExportSettings,
    MusicXmlInstrumentSpec,
)
from saxo_ai.domain.rhythm_quantization import QuantizedNoteEvent, QuantizedRhythmResult


def _text(parent: ET.Element, tag: str, value: object) -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = str(value)
    return element


def _format_decimal(value: float) -> str:
    rendered = format(Decimal(str(value)), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _add_ties(note: ET.Element, segment: MusicXmlSegment) -> None:
    if segment.tie_stop:
        ET.SubElement(note, "tie", {"type": "stop"})
    if segment.tie_start:
        ET.SubElement(note, "tie", {"type": "start"})


def _add_tied_notations(note: ET.Element, segment: MusicXmlSegment) -> None:
    if not segment.tie_stop and not segment.tie_start:
        return
    notations = ET.SubElement(note, "notations")
    if segment.tie_stop:
        ET.SubElement(notations, "tied", {"type": "stop"})
    if segment.tie_start:
        ET.SubElement(notations, "tied", {"type": "start"})


def _add_segment(measure: ET.Element, segment: MusicXmlSegment) -> None:
    note = ET.SubElement(measure, "note")
    if isinstance(segment.source, QuantizedNoteEvent):
        pitch = musicxml_pitch_for_midi(segment.source.source.written_pitch_midi)
        pitch_element = ET.SubElement(note, "pitch")
        _text(pitch_element, "step", pitch.step)
        if pitch.alter:
            _text(pitch_element, "alter", pitch.alter)
        _text(pitch_element, "octave", pitch.octave)
    else:
        ET.SubElement(note, "rest")
    _text(note, "duration", segment.duration_divisions)
    _add_ties(note, segment)
    _text(note, "voice", 1)
    _text(note, "staff", 1)
    _add_tied_notations(note, segment)


def _add_first_measure_attributes(
    measure: ET.Element,
    *,
    divisions: int,
    settings: MusicXmlExportSettings,
    instrument: MusicXmlInstrumentSpec,
) -> None:
    attributes = ET.SubElement(measure, "attributes")
    _text(attributes, "divisions", divisions)
    time = ET.SubElement(attributes, "time")
    _text(time, "beats", settings.beats_per_measure)
    _text(time, "beat-type", MUSICXML_BEAT_TYPE)
    clef = ET.SubElement(attributes, "clef")
    _text(clef, "sign", "G")
    _text(clef, "line", 2)
    transpose = ET.SubElement(attributes, "transpose")
    _text(transpose, "diatonic", instrument.diatonic)
    _text(transpose, "chromatic", instrument.chromatic)
    if instrument.octave_change is not None:
        _text(transpose, "octave-change", instrument.octave_change)


def _add_tempo_direction(measure: ET.Element, tempo_bpm: float) -> None:
    rendered_tempo = _format_decimal(tempo_bpm)
    direction = ET.SubElement(measure, "direction", {"placement": "above"})
    direction_type = ET.SubElement(direction, "direction-type")
    metronome = ET.SubElement(direction_type, "metronome")
    _text(metronome, "beat-unit", "quarter")
    _text(metronome, "per-minute", rendered_tempo)
    ET.SubElement(direction, "sound", {"tempo": rendered_tempo})


class StandardLibraryMusicXmlEncoder:
    def encode(
        self,
        *,
        original: QuantizedRhythmResult,
        settings: MusicXmlExportSettings,
        instrument: MusicXmlInstrumentSpec,
    ) -> bytes:
        plan = plan_musicxml_score(original, settings)
        root = ET.Element(MUSICXML_SCORE_TYPE, {"version": MUSICXML_DOCUMENT_VERSION})
        work = ET.SubElement(root, "work")
        _text(work, "work-title", "Saxo Transcription")

        part_list = ET.SubElement(root, "part-list")
        score_part = ET.SubElement(part_list, "score-part", {"id": "P1"})
        _text(score_part, "part-name", instrument.part_name)
        score_instrument = ET.SubElement(score_part, "score-instrument", {"id": "P1-I1"})
        _text(score_instrument, "instrument-name", instrument.part_name)

        part = ET.SubElement(root, "part", {"id": "P1"})
        for measure_plan in plan.measures:
            measure = ET.SubElement(part, "measure", {"number": str(measure_plan.number)})
            if measure_plan.number == 1:
                _add_first_measure_attributes(
                    measure,
                    divisions=plan.divisions,
                    settings=settings,
                    instrument=instrument,
                )
                _add_tempo_direction(measure, original.tempo.effective_tempo_bpm)
            for segment in measure_plan.segments:
                _add_segment(measure, segment)

        ET.indent(root, space="  ")
        return ET.tostring(
            root,
            encoding="utf-8",
            xml_declaration=True,
            short_empty_elements=True,
        )
