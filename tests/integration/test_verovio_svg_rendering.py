from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET

import pytest

from saxo_ai.application.musicxml_export import ExportQuantizedRhythmToMusicXml
from saxo_ai.application.score_rendering import RenderMusicXmlToSvg
from saxo_ai.domain.musicxml_export import MusicXmlExportSettings
from saxo_ai.domain.score_rendering import ScoreRenderSettings
from saxo_ai.infrastructure.musicxml_encoder import StandardLibraryMusicXmlEncoder
from saxo_ai.infrastructure.verovio_musicxml import VerovioMusicXmlReader
from saxo_ai.infrastructure.verovio_svg import VerovioSvgScoreRenderer
from tests.musicxml_helpers import manual_quantized

pytestmark = [pytest.mark.integration, pytest.mark.score_render_integration]


def real_musicxml(specs, *, revision: int = 1):
    quantized = manual_quantized(specs, revision=revision)
    return ExportQuantizedRhythmToMusicXml(
        StandardLibraryMusicXmlEncoder(),
        VerovioMusicXmlReader(),
    ).execute(quantized, MusicXmlExportSettings())


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def assert_valid_pages(result) -> None:
    assert result.pages
    assert [page.page_number for page in result.pages] == list(
        range(1, result.report.page_count + 1)
    )
    assert all(page.page_count == result.report.page_count for page in result.pages)
    assert result.report.total_size_bytes == sum(page.size_bytes for page in result.pages)
    for page in result.pages:
        text = page.content.decode("utf-8")
        root = ET.fromstring(text)
        assert local_name(root.tag) == "svg"
        assert page.media_type == "image/svg+xml"
        assert page.file_extension == ".svg"
        assert page.size_bytes == len(page.content)
        assert page.sha256 == hashlib.sha256(page.content).hexdigest()


def test_real_verovio_renders_deterministic_revision_linked_svg_in_memory() -> None:
    original = real_musicxml(
        (
            (60, 0.0, 0.5, 0.0, True),
            (62, 0.5, 1.0, 1.0, False),
            (64, 1.0, 1.5, 0.8, False),
        ),
        revision=6,
    )
    source_bytes = original.artifact.content
    settings = ScoreRenderSettings()
    use_case = RenderMusicXmlToSvg(VerovioSvgScoreRenderer())

    first = use_case.execute(original, settings)
    second = use_case.execute(original, settings)

    assert_valid_pages(first)
    assert first.original is original
    assert first.report.source_musicxml_sha256 == original.artifact.sha256
    assert first.report.source_tempo_revision == original.original.tempo.revision == 6
    assert [page.content for page in first.pages] == [page.content for page in second.pages]
    assert [page.sha256 for page in first.pages] == [page.sha256 for page in second.pages]
    assert first.report == second.report
    assert original.artifact.content == source_bytes


def test_real_verovio_renders_multiple_independent_svg_pages() -> None:
    specs = tuple(
        (
            60 + index % 12,
            index * 0.5,
            (index + 1) * 0.5,
            0.8,
            False,
        )
        for index in range(96)
    )
    original = real_musicxml(specs, revision=2)
    settings = ScoreRenderSettings(page_width=900, page_height=600, scale=100)

    result = RenderMusicXmlToSvg(VerovioSvgScoreRenderer()).execute(original, settings)

    assert_valid_pages(result)
    assert result.report.page_count >= 2
    assert len({page.content for page in result.pages}) == result.report.page_count
    assert all(page.content.count(b"<svg") == 1 for page in result.pages)
    assert result.original is original


def test_empty_musicxml_timeline_renders_without_inventing_music() -> None:
    original = real_musicxml((), revision=3)
    source_bytes = original.artifact.content
    source_sha = original.artifact.sha256

    result = RenderMusicXmlToSvg(VerovioSvgScoreRenderer()).execute(
        original,
        ScoreRenderSettings(),
    )

    assert_valid_pages(result)
    assert result.report.page_count >= 1
    assert result.original is original
    assert original.report.source_note_count == 0
    assert original.report.source_rest_count == 0
    assert original.validation.note_segment_count == 0
    assert original.validation.rest_segment_count == 0
    assert original.artifact.content == source_bytes
    assert original.artifact.sha256 == source_sha
