from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.rhythm_quantization import (
    QuantizedNoteEvent,
    QuantizedRest,
    QuantizedRhythmResult,
)
from saxo_ai.domain.transposition import written_pitch_offset_for

MUSICXML_EXPORT_POLICY_VERSION = "1.0"
MUSICXML_DOCUMENT_VERSION = "4.0"
MUSICXML_MEDIA_TYPE = "application/vnd.recordare.musicxml+xml"
MUSICXML_FILE_EXTENSION = ".musicxml"
MUSICXML_SCORE_TYPE = "score-partwise"
MUSICXML_PITCH_REPRESENTATION = "written"
MUSICXML_PITCH_SPELLING_POLICY = "prefer_flats"
MUSICXML_DEFAULT_BEATS_PER_MEASURE = 4
MUSICXML_BEAT_TYPE = 4


class InvalidMusicXmlExportSettingsError(ValueError):
    """Raised when manual MusicXML export settings violate their contract."""


class InvalidMusicXmlInstrumentError(ValueError):
    """Raised when a transposing-instrument description is inconsistent."""


class InvalidMusicXmlValidationSummaryError(ValueError):
    """Raised when an external-reader summary has an invalid shape."""


class InvalidMusicXmlArtifactError(ValueError):
    """Raised when MusicXML artifact metadata is structurally inconsistent."""


class InvalidMusicXmlReportError(ValueError):
    """Raised when MusicXML export counts or measure metrics are inconsistent."""


class InvalidMusicXmlResultError(ValueError):
    """Raised when a MusicXML result breaks provenance or validation invariants."""


_ErrorT = TypeVar("_ErrorT", bound=ValueError)


def _non_negative_integer(
    value: object,
    *,
    field_name: str,
    error_type: type[_ErrorT],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise error_type(f"{field_name} must be a non-negative integer")
    return value


def _positive_integer(
    value: object,
    *,
    field_name: str,
    error_type: type[_ErrorT],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise error_type(f"{field_name} must be a positive integer")
    return value


def _integer(
    value: object,
    *,
    field_name: str,
    error_type: type[_ErrorT],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise error_type(f"{field_name} must be an integer")
    return value


def _non_empty_string(
    value: object,
    *,
    field_name: str,
    error_type: type[_ErrorT],
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_type(f"{field_name} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class MusicXmlExportSettings:
    beats_per_measure: int = MUSICXML_DEFAULT_BEATS_PER_MEASURE
    policy_version: str = MUSICXML_EXPORT_POLICY_VERSION

    def __post_init__(self) -> None:
        beats = _positive_integer(
            self.beats_per_measure,
            field_name="beats_per_measure",
            error_type=InvalidMusicXmlExportSettingsError,
        )
        if self.policy_version != MUSICXML_EXPORT_POLICY_VERSION:
            raise InvalidMusicXmlExportSettingsError(
                f"policy_version must be {MUSICXML_EXPORT_POLICY_VERSION!r}"
            )
        object.__setattr__(self, "beats_per_measure", beats)


@dataclass(frozen=True, slots=True)
class MusicXmlInstrumentSpec:
    saxophone_type: SaxophoneType
    part_name: str
    diatonic: int
    chromatic: int
    octave_change: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.saxophone_type, SaxophoneType):
            raise InvalidMusicXmlInstrumentError("saxophone_type must be SaxophoneType")
        _non_empty_string(
            self.part_name,
            field_name="part_name",
            error_type=InvalidMusicXmlInstrumentError,
        )
        _integer(
            self.diatonic,
            field_name="diatonic",
            error_type=InvalidMusicXmlInstrumentError,
        )
        _integer(
            self.chromatic,
            field_name="chromatic",
            error_type=InvalidMusicXmlInstrumentError,
        )
        if self.octave_change is not None:
            _integer(
                self.octave_change,
                field_name="octave_change",
                error_type=InvalidMusicXmlInstrumentError,
            )
        expected = -written_pitch_offset_for(self.saxophone_type)
        if self.total_chromatic_transposition != expected:
            raise InvalidMusicXmlInstrumentError(
                "instrument transposition must negate the written-pitch offset"
            )

    @property
    def total_chromatic_transposition(self) -> int:
        return self.chromatic + 12 * (self.octave_change or 0)


@dataclass(frozen=True, slots=True)
class MusicXmlValidationSummary:
    document_version: str
    part_count: int
    measure_count: int
    note_segment_count: int
    rest_segment_count: int
    loaded_by_external_reader: bool

    def __post_init__(self) -> None:
        if self.document_version != MUSICXML_DOCUMENT_VERSION:
            raise InvalidMusicXmlValidationSummaryError(
                f"document_version must be {MUSICXML_DOCUMENT_VERSION!r}"
            )
        for field_name in (
            "part_count",
            "measure_count",
            "note_segment_count",
            "rest_segment_count",
        ):
            _non_negative_integer(
                getattr(self, field_name),
                field_name=field_name,
                error_type=InvalidMusicXmlValidationSummaryError,
            )
        if not isinstance(self.loaded_by_external_reader, bool):
            raise InvalidMusicXmlValidationSummaryError(
                "loaded_by_external_reader must be a boolean"
            )


@dataclass(frozen=True, slots=True)
class MusicXmlArtifact:
    content: bytes
    media_type: str
    file_extension: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.content, bytes) or not self.content:
            raise InvalidMusicXmlArtifactError("content must be non-empty bytes")
        try:
            text = self.content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise InvalidMusicXmlArtifactError("content must be valid UTF-8") from error
        if not text.startswith("<?xml") or "?>" not in text:
            raise InvalidMusicXmlArtifactError("content must begin with an XML declaration")
        declaration, body = text.split("?>", 1)
        normalized_declaration = declaration.lower().replace('"', "'")
        if "encoding='utf-8'" not in normalized_declaration:
            raise InvalidMusicXmlArtifactError("XML declaration must specify UTF-8")
        if not body.lstrip().startswith(
            f'<{MUSICXML_SCORE_TYPE} version="{MUSICXML_DOCUMENT_VERSION}"'
        ):
            raise InvalidMusicXmlArtifactError(
                "content root must be score-partwise MusicXML 4.0"
            )
        if self.media_type != MUSICXML_MEDIA_TYPE:
            raise InvalidMusicXmlArtifactError(f"media_type must be {MUSICXML_MEDIA_TYPE!r}")
        if self.file_extension != MUSICXML_FILE_EXTENSION:
            raise InvalidMusicXmlArtifactError(
                f"file_extension must be {MUSICXML_FILE_EXTENSION!r}"
            )
        size = _non_negative_integer(
            self.size_bytes,
            field_name="size_bytes",
            error_type=InvalidMusicXmlArtifactError,
        )
        if size != len(self.content):
            raise InvalidMusicXmlArtifactError("size_bytes must equal content length")
        if (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise InvalidMusicXmlArtifactError(
                "sha256 must be 64 lowercase hexadecimal characters"
            )


@dataclass(frozen=True, slots=True)
class MusicXmlExportReport:
    settings: MusicXmlExportSettings
    source_note_count: int
    source_rest_count: int
    measure_count: int
    note_segment_count: int
    rest_segment_count: int
    split_note_count: int
    split_rest_count: int
    final_measure_used_divisions: int
    measure_capacity_divisions: int

    def __post_init__(self) -> None:
        if not isinstance(self.settings, MusicXmlExportSettings):
            raise InvalidMusicXmlReportError("settings must be MusicXmlExportSettings")
        counts: dict[str, int] = {}
        for field_name in (
            "source_note_count",
            "source_rest_count",
            "note_segment_count",
            "rest_segment_count",
            "split_note_count",
            "split_rest_count",
            "final_measure_used_divisions",
        ):
            counts[field_name] = _non_negative_integer(
                getattr(self, field_name),
                field_name=field_name,
                error_type=InvalidMusicXmlReportError,
            )
        measure_count = _positive_integer(
            self.measure_count,
            field_name="measure_count",
            error_type=InvalidMusicXmlReportError,
        )
        capacity = _positive_integer(
            self.measure_capacity_divisions,
            field_name="measure_capacity_divisions",
            error_type=InvalidMusicXmlReportError,
        )
        if counts["note_segment_count"] < counts["source_note_count"]:
            raise InvalidMusicXmlReportError(
                "note_segment_count cannot be smaller than source_note_count"
            )
        if counts["rest_segment_count"] < counts["source_rest_count"]:
            raise InvalidMusicXmlReportError(
                "rest_segment_count cannot be smaller than source_rest_count"
            )
        if counts["split_note_count"] > counts["source_note_count"]:
            raise InvalidMusicXmlReportError("split_note_count cannot exceed source_note_count")
        if counts["split_rest_count"] > counts["source_rest_count"]:
            raise InvalidMusicXmlReportError("split_rest_count cannot exceed source_rest_count")
        if counts["final_measure_used_divisions"] > capacity:
            raise InvalidMusicXmlReportError(
                "final_measure_used_divisions cannot exceed measure capacity"
            )
        object.__setattr__(self, "measure_count", measure_count)
        object.__setattr__(self, "measure_capacity_divisions", capacity)


@dataclass(frozen=True, slots=True)
class MusicXmlExportResult:
    original: QuantizedRhythmResult
    instrument: MusicXmlInstrumentSpec
    artifact: MusicXmlArtifact
    validation: MusicXmlValidationSummary
    report: MusicXmlExportReport

    def __post_init__(self) -> None:
        if not isinstance(self.original, QuantizedRhythmResult):
            raise InvalidMusicXmlResultError("original must be a QuantizedRhythmResult")
        if not isinstance(self.instrument, MusicXmlInstrumentSpec):
            raise InvalidMusicXmlResultError("instrument must be MusicXmlInstrumentSpec")
        if not isinstance(self.artifact, MusicXmlArtifact):
            raise InvalidMusicXmlResultError("artifact must be MusicXmlArtifact")
        if not isinstance(self.validation, MusicXmlValidationSummary):
            raise InvalidMusicXmlResultError("validation must be MusicXmlValidationSummary")
        if not isinstance(self.report, MusicXmlExportReport):
            raise InvalidMusicXmlResultError("report must be MusicXmlExportReport")
        if self.instrument.saxophone_type is not self.original.tempo.original.saxophone_type:
            raise InvalidMusicXmlResultError(
                "instrument must match the quantized result saxophone type"
            )

        source_note_count = sum(
            isinstance(item, QuantizedNoteEvent) for item in self.original.timeline
        )
        source_rest_count = sum(isinstance(item, QuantizedRest) for item in self.original.timeline)
        if self.report.source_note_count != source_note_count:
            raise InvalidMusicXmlResultError("report source note count must match the timeline")
        if self.report.source_rest_count != source_rest_count:
            raise InvalidMusicXmlResultError("report source rest count must match the timeline")
        if not self.validation.loaded_by_external_reader:
            raise InvalidMusicXmlResultError("external reader must load the document")
        if self.validation.part_count != 1:
            raise InvalidMusicXmlResultError("MusicXML must contain exactly one part")
        expected = (
            (self.validation.measure_count, self.report.measure_count, "measure_count"),
            (
                self.validation.note_segment_count,
                self.report.note_segment_count,
                "note_segment_count",
            ),
            (
                self.validation.rest_segment_count,
                self.report.rest_segment_count,
                "rest_segment_count",
            ),
        )
        for actual, reported, field_name in expected:
            if actual != reported:
                raise InvalidMusicXmlResultError(
                    f"external validation {field_name} must match the export report"
                )
