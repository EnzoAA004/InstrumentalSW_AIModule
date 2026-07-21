from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, cast

import pytest

from saxo_ai.application.musicxml_export import (
    ExportQuantizedRhythmToMusicXml,
    MusicXmlEncodingError,
    MusicXmlReaderError,
    MusicXmlValidationError,
)
from saxo_ai.domain.musicxml_export import (
    InvalidMusicXmlArtifactError,
    InvalidMusicXmlResultError,
    MusicXmlExportResult,
    MusicXmlExportSettings,
    MusicXmlValidationSummary,
)
from saxo_ai.domain.rhythm_quantization import QuantizedRhythmResult
from saxo_ai.infrastructure.musicxml_encoder import StandardLibraryMusicXmlEncoder
from tests.musicxml_helpers import manual_quantized

ROOT = Path(__file__).resolve().parents[2]


class ParsingReader:
    def validate(self, *, content: bytes) -> MusicXmlValidationSummary:
        root = ET.fromstring(content)
        notes = root.findall("./part/measure/note")
        rests = sum(note.find("rest") is not None for note in notes)
        return MusicXmlValidationSummary(
            document_version=root.attrib["version"],
            part_count=len(root.findall("./part")),
            measure_count=len(root.findall("./part/measure")),
            note_segment_count=len(notes) - rests,
            rest_segment_count=rests,
            loaded_by_external_reader=True,
        )


class ConstantEncoder:
    def __init__(self, value: object) -> None:
        self.value = value

    def encode(self, *, original: object, settings: object, instrument: object) -> object:
        del original, settings, instrument
        return self.value


class RaisingEncoder:
    def encode(self, *, original: object, settings: object, instrument: object) -> bytes:
        del original, settings, instrument
        raise LookupError("internal encoder detail")


class ConstantReader:
    def __init__(self, value: object) -> None:
        self.value = value

    def validate(self, *, content: bytes) -> object:
        del content
        return self.value


class RaisingReader:
    def validate(self, *, content: bytes) -> MusicXmlValidationSummary:
        del content
        raise LookupError("external reader detail")


def valid_original() -> QuantizedRhythmResult:
    return manual_quantized(
        (
            (60, 0.0, 0.5, 0.0, True),
            (62, 0.75, 1.0, 1.0, False),
        ),
        bpm=120.0,
        revision=3,
    )


def export(
    original: QuantizedRhythmResult | None = None,
) -> MusicXmlExportResult:
    return ExportQuantizedRhythmToMusicXml(
        StandardLibraryMusicXmlEncoder(),
        ParsingReader(),
    ).execute(original or valid_original(), MusicXmlExportSettings())


def test_artifact_has_exact_bytes_size_sha_and_is_deterministic() -> None:
    original = valid_original()
    first = export(original)
    second = export(original)

    assert first.original is original
    assert first.artifact.content.startswith(b"<?xml version='1.0' encoding='utf-8'?>")
    assert first.artifact.media_type == "application/vnd.recordare.musicxml+xml"
    assert first.artifact.file_extension == ".musicxml"
    assert first.artifact.size_bytes == len(first.artifact.content)
    assert first.artifact.sha256 == hashlib.sha256(first.artifact.content).hexdigest()
    assert first.artifact == second.artifact
    assert first.report == second.report
    assert first.validation == second.validation


def test_result_preserves_complete_source_and_exact_revision_chain() -> None:
    original = valid_original()
    result = export(original)
    raw = original.tempo.original.original.original.original

    assert result.original is original
    assert result.original.tempo.revision == 3
    assert result.original.tempo.effective_tempo_bpm == 120.0
    assert result.original.tempo.source.value == "manual"
    assert result.original.tempo.automatic_estimate is None
    assert result.instrument.saxophone_type is original.tempo.original.saxophone_type
    assert raw.model.engine_name == "filosax"
    assert raw.model.engine_source_revision == "a" * 40
    assert raw.model.model_revision == "b" * 40
    assert raw.model.checkpoint_sha256 == "c" * 64
    assert raw.settings.sample_rate_hz == 16_000
    first_source = original.tempo.original.events[0]
    assert first_source.source.event.pitch_concert_midi == 60
    assert first_source.written_pitch_midi == 69
    assert first_source.source.event.confidence == 0.0
    assert first_source.source.is_low_confidence is True
    assert original.tempo.original.original.report.low_confidence_count == 1
    assert original.tempo.original.original.original.report.input_event_count == 2
    assert original.report.quantized_note_count == 2


def test_two_tempo_revisions_keep_distinct_original_results() -> None:
    first_quantized = manual_quantized(((60, 0.125, 0.5, 0.8, False),), bpm=120.0, revision=1)
    second_quantized = manual_quantized(((60, 0.125, 0.5, 0.8, False),), bpm=60.0, revision=2)

    first = export(first_quantized)
    second = export(second_quantized)

    assert first.original is first_quantized
    assert second.original is second_quantized
    assert first.original.tempo.revision == 1
    assert second.original.tempo.revision == 2
    assert first.artifact.content != second.artifact.content
    assert first.artifact.sha256 != second.artifact.sha256


@pytest.mark.parametrize(
    "value",
    [
        "not bytes",
        b"",
        b"not xml",
        b"<?xml version='1.0' encoding='utf-8'?><score-timewise version='4.0'/>",
    ],
)
def test_invalid_encoder_outputs_are_rejected(value: object) -> None:
    use_case = ExportQuantizedRhythmToMusicXml(
        cast(Any, ConstantEncoder(value)),
        ParsingReader(),
    )
    with pytest.raises((MusicXmlEncodingError, InvalidMusicXmlArtifactError)):
        use_case.execute(valid_original(), MusicXmlExportSettings())


def test_unexpected_encoder_failure_is_wrapped_with_cause() -> None:
    use_case = ExportQuantizedRhythmToMusicXml(RaisingEncoder(), ParsingReader())
    with pytest.raises(MusicXmlEncodingError) as captured:
        use_case.execute(valid_original(), MusicXmlExportSettings())
    assert isinstance(captured.value.__cause__, LookupError)
    assert "internal encoder detail" not in str(captured.value)


def test_unexpected_reader_failure_is_wrapped_with_cause() -> None:
    use_case = ExportQuantizedRhythmToMusicXml(StandardLibraryMusicXmlEncoder(), RaisingReader())
    with pytest.raises(MusicXmlReaderError) as captured:
        use_case.execute(valid_original(), MusicXmlExportSettings())
    assert isinstance(captured.value.__cause__, LookupError)
    assert "external reader detail" not in str(captured.value)


@pytest.mark.parametrize(
    "value",
    [
        object(),
        MusicXmlValidationSummary("4.0", 1, 1, 1, 1, False),
        MusicXmlValidationSummary("4.0", 2, 1, 1, 1, True),
        MusicXmlValidationSummary("4.0", 1, 99, 1, 1, True),
        MusicXmlValidationSummary("4.0", 1, 1, 99, 1, True),
        MusicXmlValidationSummary("4.0", 1, 1, 1, 99, True),
    ],
)
def test_reader_type_load_and_count_inconsistencies_are_rejected(value: object) -> None:
    use_case = ExportQuantizedRhythmToMusicXml(
        StandardLibraryMusicXmlEncoder(),
        cast(Any, ConstantReader(value)),
    )
    with pytest.raises((MusicXmlReaderError, MusicXmlValidationError, InvalidMusicXmlResultError)):
        use_case.execute(valid_original(), MusicXmlExportSettings())


def test_architecture_and_scope_boundaries() -> None:
    domain = (ROOT / "src/saxo_ai/domain/musicxml_export.py").read_text().lower()
    application = (ROOT / "src/saxo_ai/application/musicxml_export.py").read_text().lower()
    encoder = (ROOT / "src/saxo_ai/infrastructure/musicxml_encoder.py").read_text().lower()
    reader = (ROOT / "src/saxo_ai/infrastructure/verovio_musicxml.py").read_text().lower()
    pyproject = (ROOT / "pyproject.toml").read_text().lower()
    workflow = (ROOT / ".github/workflows/quality.yml").read_text()
    routes = (ROOT / "src/saxo_ai/api/routes.py").read_text().lower()
    main = (ROOT / "src/saxo_ai/main.py").read_text().lower()

    for forbidden in ("verovio", "elementtree", "hashlib", "fastapi", "import xml"):
        assert forbidden not in domain
    assert "verovio" not in application
    assert "hashlib" in application
    assert "elementtree" in encoder
    assert "import verovio" in reader
    assert '"verovio==6.2.1"' in pyproject
    assert "rendertosvg" not in encoder + reader + application + domain
    assert "svg" not in domain + application
    assert "pdf" not in domain + application
    assert "musicxml" not in routes
    assert "musicxml" not in main
    assert '"3.11"' in workflow and '"3.12"' in workflow and '"3.13"' in workflow
    assert "sax-035" not in domain + application + encoder + reader
