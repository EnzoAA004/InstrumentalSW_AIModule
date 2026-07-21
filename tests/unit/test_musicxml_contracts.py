from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from saxo_ai.application.musicxml_export import musicxml_instrument_spec_for
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.musicxml_export import (
    MUSICXML_BEAT_TYPE,
    MUSICXML_DEFAULT_BEATS_PER_MEASURE,
    MUSICXML_DOCUMENT_VERSION,
    MUSICXML_EXPORT_POLICY_VERSION,
    MUSICXML_FILE_EXTENSION,
    MUSICXML_MEDIA_TYPE,
    MUSICXML_PITCH_REPRESENTATION,
    MUSICXML_PITCH_SPELLING_POLICY,
    MUSICXML_SCORE_TYPE,
    InvalidMusicXmlArtifactError,
    InvalidMusicXmlExportSettingsError,
    InvalidMusicXmlInstrumentError,
    InvalidMusicXmlReportError,
    MusicXmlArtifact,
    MusicXmlExportReport,
    MusicXmlExportSettings,
    MusicXmlInstrumentSpec,
)
from saxo_ai.domain.transposition import written_pitch_offset_for


def test_constants_and_default_settings_are_stable() -> None:
    settings = MusicXmlExportSettings()

    assert MUSICXML_EXPORT_POLICY_VERSION == "1.0"
    assert MUSICXML_DOCUMENT_VERSION == "4.0"
    assert MUSICXML_MEDIA_TYPE == "application/vnd.recordare.musicxml+xml"
    assert MUSICXML_FILE_EXTENSION == ".musicxml"
    assert MUSICXML_SCORE_TYPE == "score-partwise"
    assert MUSICXML_PITCH_REPRESENTATION == "written"
    assert MUSICXML_PITCH_SPELLING_POLICY == "prefer_flats"
    assert MUSICXML_DEFAULT_BEATS_PER_MEASURE == settings.beats_per_measure == 4
    assert MUSICXML_BEAT_TYPE == 4


@pytest.mark.parametrize("beats", [3, 4, 5])
def test_settings_accept_positive_quarter_note_measures(beats: int) -> None:
    settings = MusicXmlExportSettings(beats_per_measure=beats)
    assert settings.beats_per_measure == beats
    assert settings.policy_version == "1.0"


@pytest.mark.parametrize("value", [0, -1, True, False, 4.0, "4", None])
def test_settings_reject_invalid_beats_per_measure(value: object) -> None:
    with pytest.raises(InvalidMusicXmlExportSettingsError):
        MusicXmlExportSettings(beats_per_measure=cast(Any, value))


def test_settings_reject_unknown_version_and_are_immutable() -> None:
    with pytest.raises(InvalidMusicXmlExportSettingsError):
        MusicXmlExportSettings(policy_version="2.0")

    settings = MusicXmlExportSettings()
    assert not hasattr(settings, "__dict__")
    with pytest.raises(FrozenInstanceError):
        settings.beats_per_measure = 3  # type: ignore[misc]


@pytest.mark.parametrize(
    ("saxophone_type", "name", "diatonic", "chromatic", "octave_change", "total"),
    [
        (SaxophoneType.SOPRANO, "Soprano Saxophone in B-flat", -1, -2, None, -2),
        (SaxophoneType.ALTO, "Alto Saxophone in E-flat", -5, -9, None, -9),
        (SaxophoneType.TENOR, "Tenor Saxophone in B-flat", -1, -2, -1, -14),
        (SaxophoneType.BARITONE, "Baritone Saxophone in E-flat", -5, -9, -1, -21),
    ],
)
def test_instrument_specs_match_written_pitch_offsets(
    saxophone_type: SaxophoneType,
    name: str,
    diatonic: int,
    chromatic: int,
    octave_change: int | None,
    total: int,
) -> None:
    spec = musicxml_instrument_spec_for(saxophone_type)

    assert spec == MusicXmlInstrumentSpec(
        saxophone_type,
        name,
        diatonic,
        chromatic,
        octave_change,
    )
    assert spec.total_chromatic_transposition == total
    assert total == -written_pitch_offset_for(saxophone_type)


@pytest.mark.parametrize(
    "changes",
    [
        {"saxophone_type": "alto"},
        {"part_name": ""},
        {"part_name": "  "},
        {"diatonic": True},
        {"chromatic": -8},
        {"octave_change": True},
    ],
)
def test_invalid_instrument_specs_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "saxophone_type": SaxophoneType.ALTO,
        "part_name": "Alto Saxophone in E-flat",
        "diatonic": -5,
        "chromatic": -9,
        "octave_change": None,
    }
    values.update(changes)
    with pytest.raises(InvalidMusicXmlInstrumentError):
        MusicXmlInstrumentSpec(**cast(Any, values))


def test_artifact_validates_shape_without_calculating_digest() -> None:
    content = (
        b"<?xml version='1.0' encoding='utf-8'?>\n<score-partwise version=\"4.0\"></score-partwise>"
    )
    artifact = MusicXmlArtifact(
        content=content,
        media_type=MUSICXML_MEDIA_TYPE,
        file_extension=MUSICXML_FILE_EXTENSION,
        size_bytes=len(content),
        sha256="a" * 64,
    )

    assert artifact.content is content
    assert artifact.size_bytes == len(content)


@pytest.mark.parametrize(
    "changes",
    [
        {"content": "xml"},
        {"content": b""},
        {"content": b"<score-partwise/>"},
        {"content": b"<?xml version='1.0' encoding='utf-8'?><score-timewise/>"},
        {"media_type": "application/xml"},
        {"file_extension": ".mxl"},
        {"size_bytes": 1},
        {"sha256": "A" * 64},
        {"sha256": "a" * 63},
    ],
)
def test_invalid_artifacts_are_rejected(changes: dict[str, object]) -> None:
    content = (
        b"<?xml version='1.0' encoding='utf-8'?>\n<score-partwise version=\"4.0\"></score-partwise>"
    )
    values: dict[str, object] = {
        "content": content,
        "media_type": MUSICXML_MEDIA_TYPE,
        "file_extension": MUSICXML_FILE_EXTENSION,
        "size_bytes": len(content),
        "sha256": "a" * 64,
    }
    values.update(changes)
    with pytest.raises(InvalidMusicXmlArtifactError):
        MusicXmlArtifact(**cast(Any, values))


def test_report_accepts_empty_timeline_contract() -> None:
    report = MusicXmlExportReport(
        settings=MusicXmlExportSettings(),
        source_note_count=0,
        source_rest_count=0,
        measure_count=1,
        note_segment_count=0,
        rest_segment_count=0,
        split_note_count=0,
        split_rest_count=0,
        final_measure_used_divisions=0,
        measure_capacity_divisions=16,
    )
    assert report.measure_count == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"settings": object()},
        {"source_note_count": -1},
        {"measure_count": 0},
        {"note_segment_count": 0},
        {"split_note_count": 2},
        {"final_measure_used_divisions": 17},
        {"measure_capacity_divisions": 0},
    ],
)
def test_invalid_reports_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "settings": MusicXmlExportSettings(),
        "source_note_count": 1,
        "source_rest_count": 0,
        "measure_count": 1,
        "note_segment_count": 1,
        "rest_segment_count": 0,
        "split_note_count": 0,
        "split_rest_count": 0,
        "final_measure_used_divisions": 4,
        "measure_capacity_divisions": 16,
    }
    values.update(changes)
    with pytest.raises(InvalidMusicXmlReportError):
        MusicXmlExportReport(**cast(Any, values))
