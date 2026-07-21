from __future__ import annotations

from pathlib import Path

import pytest
import verovio

from saxo_ai.application.musicxml_export import ExportQuantizedRhythmToMusicXml
from saxo_ai.domain.musicxml_export import MusicXmlExportSettings
from saxo_ai.infrastructure.musicxml_encoder import StandardLibraryMusicXmlEncoder
from saxo_ai.infrastructure.verovio_musicxml import VerovioMusicXmlReader
from tests.musicxml_helpers import manual_quantized

pytestmark = (pytest.mark.integration, pytest.mark.musicxml_integration)


def configured_toolkit() -> verovio.toolkit:
    toolkit = verovio.toolkit()
    toolkit.setOptions({"inputFrom": "xml", "xmlIdSeed": 0})
    return toolkit


def test_musicxml_loads_from_memory_and_disk_without_rendering(tmp_path: Path) -> None:
    original = manual_quantized(
        (
            (60, 0.25, 0.5, 0.0, True),
            (62, 0.75, 2.5, 1.0, False),
        ),
        bpm=108.5,
    )
    result = ExportQuantizedRhythmToMusicXml(
        StandardLibraryMusicXmlEncoder(),
        VerovioMusicXmlReader(),
    ).execute(original, MusicXmlExportSettings())

    assert result.validation.loaded_by_external_reader is True
    assert result.validation.part_count == 1
    assert result.validation.measure_count == result.report.measure_count
    assert result.validation.note_segment_count == result.report.note_segment_count
    assert result.validation.rest_segment_count == result.report.rest_segment_count

    text = result.artifact.content.decode("utf-8")
    memory_toolkit = configured_toolkit()
    assert memory_toolkit.loadData(text) is True
    memory_mei = memory_toolkit.getMEI()
    assert isinstance(memory_mei, str)
    assert memory_mei.strip().startswith("<?xml") or "<mei" in memory_mei

    path = tmp_path / "transcription.musicxml"
    path.write_bytes(result.artifact.content)
    disk_toolkit = configured_toolkit()
    assert disk_toolkit.loadFile(str(path)) is True
    disk_mei = disk_toolkit.getMEI()
    assert isinstance(disk_mei, str)
    assert "<mei" in disk_mei
