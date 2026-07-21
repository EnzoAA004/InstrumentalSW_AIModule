from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, runtime_checkable

from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.musicxml_export import (
    MUSICXML_FILE_EXTENSION,
    MUSICXML_MEDIA_TYPE,
    InvalidMusicXmlArtifactError,
    InvalidMusicXmlExportSettingsError,
    InvalidMusicXmlInstrumentError,
    InvalidMusicXmlReportError,
    InvalidMusicXmlResultError,
    InvalidMusicXmlValidationSummaryError,
    MusicXmlArtifact,
    MusicXmlExportReport,
    MusicXmlExportResult,
    MusicXmlExportSettings,
    MusicXmlInstrumentSpec,
    MusicXmlValidationSummary,
)
from saxo_ai.domain.rhythm_quantization import (
    QuantizedNoteEvent,
    QuantizedRest,
    QuantizedRhythmResult,
    QuantizedTimelineItem,
)


class MusicXmlEncodingError(RuntimeError):
    """Raised when the replaceable MusicXML encoder cannot create bytes."""


class MusicXmlReaderError(RuntimeError):
    """Raised when the external MusicXML reader fails unexpectedly."""


class MusicXmlValidationError(ValueError):
    """Raised when external validation disagrees with the export contract."""


@runtime_checkable
class MusicXmlEncoder(Protocol):
    def encode(
        self,
        *,
        original: QuantizedRhythmResult,
        settings: MusicXmlExportSettings,
        instrument: MusicXmlInstrumentSpec,
    ) -> bytes: ...


@runtime_checkable
class MusicXmlReader(Protocol):
    def validate(self, *, content: bytes) -> MusicXmlValidationSummary: ...


@dataclass(frozen=True, slots=True)
class MusicXmlPitch:
    step: str
    alter: int
    octave: int


_PITCH_CLASS_SPELLINGS: tuple[tuple[str, int], ...] = (
    ("C", 0),
    ("D", -1),
    ("D", 0),
    ("E", -1),
    ("E", 0),
    ("F", 0),
    ("G", -1),
    ("G", 0),
    ("A", -1),
    ("A", 0),
    ("B", -1),
    ("B", 0),
)


def musicxml_pitch_for_midi(value: object) -> MusicXmlPitch:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 127:
        raise ValueError("written MIDI pitch must be an integer between 0 and 127")
    step, alter = _PITCH_CLASS_SPELLINGS[value % 12]
    return MusicXmlPitch(step=step, alter=alter, octave=value // 12 - 1)


_INSTRUMENT_FIELDS: dict[SaxophoneType, tuple[str, int, int, int | None]] = {
    SaxophoneType.SOPRANO: ("Soprano Saxophone in B-flat", -1, -2, None),
    SaxophoneType.ALTO: ("Alto Saxophone in E-flat", -5, -9, None),
    SaxophoneType.TENOR: ("Tenor Saxophone in B-flat", -1, -2, -1),
    SaxophoneType.BARITONE: ("Baritone Saxophone in E-flat", -5, -9, -1),
}


def musicxml_instrument_spec_for(value: object) -> MusicXmlInstrumentSpec:
    if not isinstance(value, SaxophoneType):
        raise InvalidMusicXmlInstrumentError("saxophone_type must be SaxophoneType")
    part_name, diatonic, chromatic, octave_change = _INSTRUMENT_FIELDS[value]
    return MusicXmlInstrumentSpec(
        saxophone_type=value,
        part_name=part_name,
        diatonic=diatonic,
        chromatic=chromatic,
        octave_change=octave_change,
    )


@dataclass(frozen=True, slots=True)
class MusicXmlSegment:
    measure_number: int
    duration_divisions: int
    source: QuantizedTimelineItem
    source_sequence_index: int
    segment_index: int
    segment_count: int

    @property
    def tie_stop(self) -> bool:
        return isinstance(self.source, QuantizedNoteEvent) and self.segment_index > 0

    @property
    def tie_start(self) -> bool:
        return (
            isinstance(self.source, QuantizedNoteEvent)
            and self.segment_index < self.segment_count - 1
        )


@dataclass(frozen=True, slots=True)
class MusicXmlMeasurePlan:
    number: int
    segments: tuple[MusicXmlSegment, ...]


@dataclass(frozen=True, slots=True)
class MusicXmlScorePlan:
    divisions: int
    measure_capacity_divisions: int
    measures: tuple[MusicXmlMeasurePlan, ...]
    report: MusicXmlExportReport


def _timeline_bounds(item: QuantizedTimelineItem) -> tuple[int, int]:
    if isinstance(item, QuantizedNoteEvent):
        return item.quantized_onset_step, item.quantized_offset_step
    return item.onset_step, item.offset_step


def _segments_for_item(
    item: QuantizedTimelineItem,
    *,
    source_sequence_index: int,
    measure_capacity: int,
) -> tuple[MusicXmlSegment, ...]:
    start, end = _timeline_bounds(item)
    drafts: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        measure_number = cursor // measure_capacity + 1
        measure_end = measure_number * measure_capacity
        segment_end = min(end, measure_end)
        drafts.append((measure_number, segment_end - cursor))
        cursor = segment_end
    segment_count = len(drafts)
    return tuple(
        MusicXmlSegment(
            measure_number=measure_number,
            duration_divisions=duration,
            source=item,
            source_sequence_index=source_sequence_index,
            segment_index=index,
            segment_count=segment_count,
        )
        for index, (measure_number, duration) in enumerate(drafts)
    )


def plan_musicxml_score(
    original: QuantizedRhythmResult,
    settings: MusicXmlExportSettings,
) -> MusicXmlScorePlan:
    if not isinstance(original, QuantizedRhythmResult):
        raise InvalidMusicXmlResultError("original must be a QuantizedRhythmResult")
    if not isinstance(settings, MusicXmlExportSettings):
        raise InvalidMusicXmlExportSettingsError("settings must be MusicXmlExportSettings")

    divisions = original.report.settings.subdivisions_per_beat
    capacity = settings.beats_per_measure * divisions
    all_segments: list[MusicXmlSegment] = []
    segment_counts: list[int] = []
    for source_sequence_index, item in enumerate(original.timeline):
        item_segments = _segments_for_item(
            item,
            source_sequence_index=source_sequence_index,
            measure_capacity=capacity,
        )
        all_segments.extend(item_segments)
        segment_counts.append(len(item_segments))

    if original.timeline:
        _, timeline_end = _timeline_bounds(original.timeline[-1])
        measure_count = (timeline_end - 1) // capacity + 1
        final_used = timeline_end - (measure_count - 1) * capacity
    else:
        measure_count = 1
        final_used = 0

    grouped: list[list[MusicXmlSegment]] = [[] for _ in range(measure_count)]
    for segment in all_segments:
        grouped[segment.measure_number - 1].append(segment)
    measures = tuple(
        MusicXmlMeasurePlan(number=index + 1, segments=tuple(segments))
        for index, segments in enumerate(grouped)
    )

    source_note_count = sum(
        isinstance(item, QuantizedNoteEvent) for item in original.timeline
    )
    source_rest_count = sum(isinstance(item, QuantizedRest) for item in original.timeline)
    note_segment_count = sum(
        isinstance(segment.source, QuantizedNoteEvent) for segment in all_segments
    )
    rest_segment_count = len(all_segments) - note_segment_count
    split_note_count = sum(
        count > 1 and isinstance(item, QuantizedNoteEvent)
        for item, count in zip(original.timeline, segment_counts)
    )
    split_rest_count = sum(
        count > 1 and isinstance(item, QuantizedRest)
        for item, count in zip(original.timeline, segment_counts)
    )
    report = MusicXmlExportReport(
        settings=settings,
        source_note_count=source_note_count,
        source_rest_count=source_rest_count,
        measure_count=measure_count,
        note_segment_count=note_segment_count,
        rest_segment_count=rest_segment_count,
        split_note_count=split_note_count,
        split_rest_count=split_rest_count,
        final_measure_used_divisions=final_used,
        measure_capacity_divisions=capacity,
    )
    return MusicXmlScorePlan(
        divisions=divisions,
        measure_capacity_divisions=capacity,
        measures=measures,
        report=report,
    )


def build_musicxml_artifact(content: bytes) -> MusicXmlArtifact:
    return MusicXmlArtifact(
        content=content,
        media_type=MUSICXML_MEDIA_TYPE,
        file_extension=MUSICXML_FILE_EXTENSION,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
    )


_CONTROLLED_ERRORS = (
    InvalidMusicXmlArtifactError,
    InvalidMusicXmlExportSettingsError,
    InvalidMusicXmlInstrumentError,
    InvalidMusicXmlReportError,
    InvalidMusicXmlResultError,
    InvalidMusicXmlValidationSummaryError,
    MusicXmlEncodingError,
    MusicXmlReaderError,
    MusicXmlValidationError,
)


class ExportQuantizedRhythmToMusicXml:
    def __init__(self, encoder: MusicXmlEncoder, reader: MusicXmlReader) -> None:
        if not isinstance(encoder, MusicXmlEncoder):
            raise TypeError("encoder must implement MusicXmlEncoder")
        if not isinstance(reader, MusicXmlReader):
            raise TypeError("reader must implement MusicXmlReader")
        self._encoder = encoder
        self._reader = reader

    def execute(
        self,
        original: QuantizedRhythmResult,
        settings: MusicXmlExportSettings,
    ) -> MusicXmlExportResult:
        if not isinstance(original, QuantizedRhythmResult):
            raise InvalidMusicXmlResultError("original must be a QuantizedRhythmResult")
        if not isinstance(settings, MusicXmlExportSettings):
            raise InvalidMusicXmlExportSettingsError("settings must be MusicXmlExportSettings")
        instrument = musicxml_instrument_spec_for(original.tempo.original.saxophone_type)
        plan = plan_musicxml_score(original, settings)
        try:
            content = self._encoder.encode(
                original=original,
                settings=settings,
                instrument=instrument,
            )
        except _CONTROLLED_ERRORS:
            raise
        except Exception as error:
            raise MusicXmlEncodingError("MusicXML encoding failed.") from error
        if not isinstance(content, bytes):
            raise MusicXmlEncodingError("MusicXML encoder must return bytes.")
        artifact = build_musicxml_artifact(content)
        try:
            validation = self._reader.validate(content=artifact.content)
        except _CONTROLLED_ERRORS:
            raise
        except Exception as error:
            raise MusicXmlReaderError("MusicXML external validation failed.") from error
        if not isinstance(validation, MusicXmlValidationSummary):
            raise MusicXmlReaderError(
                "MusicXML reader must return MusicXmlValidationSummary."
            )
        if not validation.loaded_by_external_reader:
            raise MusicXmlValidationError("External reader did not load the MusicXML document.")
        expected = (
            (validation.part_count, 1, "part_count"),
            (validation.measure_count, plan.report.measure_count, "measure_count"),
            (
                validation.note_segment_count,
                plan.report.note_segment_count,
                "note_segment_count",
            ),
            (
                validation.rest_segment_count,
                plan.report.rest_segment_count,
                "rest_segment_count",
            ),
        )
        for actual, required, field_name in expected:
            if actual != required:
                raise MusicXmlValidationError(
                    f"External reader {field_name} is inconsistent with the export plan."
                )
        return MusicXmlExportResult(
            original=original,
            instrument=instrument,
            artifact=artifact,
            validation=validation,
            report=plan.report,
        )
