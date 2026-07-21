from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import pytest

from saxo_ai.application.score_rendering import (
    InvalidScoreRendererOutputError,
    RenderMusicXmlToSvg,
    ScorePageCountError,
    ScorePageRenderingError,
    ScoreRenderer,
    ScoreRendererLoadError,
    ScoreRendererLog,
    ScoreRendererOutput,
    ScoreRendererPage,
    ScoreRenderingError,
)
from saxo_ai.domain.score_rendering import ScoreRenderSettings
from tests.score_render_helpers import midi_result, musicxml_result, upstream_snapshot

ROOT = Path(__file__).resolve().parents[2]


def svg(page_number: int) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'data-page="{page_number}" viewBox="0 0 100 100"><g id="p{page_number}"/></svg>'
    ).encode()


class RecordingRenderer:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls: list[tuple[bytes, ScoreRenderSettings]] = []

    def render(self, *, content: bytes, settings: ScoreRenderSettings) -> ScoreRendererOutput:
        self.calls.append((content, settings))
        return cast(ScoreRendererOutput, self.output)


class RaisingRenderer:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def render(self, *, content: bytes, settings: ScoreRenderSettings) -> ScoreRendererOutput:
        del content, settings
        self.calls += 1
        raise self.error


def output(page_count: int = 1) -> ScoreRendererOutput:
    return ScoreRendererOutput(
        pages=tuple(ScoreRendererPage(index, svg(index)) for index in range(1, page_count + 1)),
        logs=(
            ScoreRendererLog("load", None, "load warning"),
            ScoreRendererLog("page_count", None, "count warning"),
            ScoreRendererLog("render_page", 1, "page warning"),
        ),
    )


def test_renderer_protocol_is_runtime_checkable() -> None:
    assert isinstance(RecordingRenderer(output()), ScoreRenderer)


def test_use_case_calls_renderer_once_and_builds_revision_linked_pages() -> None:
    original = musicxml_result(revision=4)
    settings = ScoreRenderSettings(page_width=800, page_height=1000, scale=75)
    renderer = RecordingRenderer(output(2))

    result = RenderMusicXmlToSvg(renderer).execute(original, settings)

    assert renderer.calls == [(original.artifact.content, settings)]
    assert result.original is original
    assert [page.page_number for page in result.pages] == [1, 2]
    assert all(page.page_count == 2 for page in result.pages)
    assert [page.content for page in result.pages] == [svg(1), svg(2)]
    assert [page.sha256 for page in result.pages] == [
        hashlib.sha256(svg(1)).hexdigest(),
        hashlib.sha256(svg(2)).hexdigest(),
    ]
    assert result.report.settings is settings
    assert result.report.page_count == 2
    assert result.report.total_size_bytes == len(svg(1)) + len(svg(2))
    assert result.report.source_musicxml_sha256 == original.artifact.sha256
    assert result.report.source_tempo_revision == original.original.tempo.revision == 4
    assert [entry.stage for entry in result.diagnostics.logs] == [
        "load",
        "page_count",
        "render_page",
    ]


def test_same_input_settings_and_renderer_output_are_deterministic() -> None:
    original = musicxml_result(revision=3)
    settings = ScoreRenderSettings()
    renderer = RecordingRenderer(output(2))
    use_case = RenderMusicXmlToSvg(renderer)

    first = use_case.execute(original, settings)
    second = use_case.execute(original, settings)

    assert first.pages == second.pages
    assert first.report == second.report
    assert first.diagnostics == second.diagnostics
    assert len(renderer.calls) == 2


@pytest.mark.parametrize(
    "invalid_output",
    [
        object(),
        ScoreRendererOutput((), ()),
        ScoreRendererOutput((ScoreRendererPage(2, svg(2)), ScoreRendererPage(1, svg(1))), ()),
        ScoreRendererOutput((ScoreRendererPage(1, svg(1)), ScoreRendererPage(1, svg(1))), ()),
        ScoreRendererOutput((ScoreRendererPage(1, b""),), ()),
        ScoreRendererOutput((ScoreRendererPage(1, b"<svg"),), ()),
        ScoreRendererOutput((ScoreRendererPage(1, b"<html/>"),), ()),
        ScoreRendererOutput((ScoreRendererPage(1, cast(Any, "not bytes")),), ()),
        ScoreRendererOutput((ScoreRendererPage(True, svg(1)),), ()),
        ScoreRendererOutput((ScoreRendererPage(1, svg(1)),), (cast(Any, object()),)),
    ],
)
def test_invalid_renderer_outputs_are_rejected_atomically(invalid_output: object) -> None:
    original = musicxml_result()
    renderer = RecordingRenderer(invalid_output)

    with pytest.raises(InvalidScoreRendererOutputError):
        RenderMusicXmlToSvg(renderer).execute(original, ScoreRenderSettings())

    assert len(renderer.calls) == 1


def test_unexpected_renderer_exception_is_wrapped_with_cause_and_stable_message() -> None:
    error = LookupError("private renderer detail")
    renderer = RaisingRenderer(error)

    with pytest.raises(ScoreRenderingError) as captured:
        RenderMusicXmlToSvg(renderer).execute(musicxml_result(), ScoreRenderSettings())

    assert captured.value.__cause__ is error
    assert captured.value.stage == "render"
    assert captured.value.page_number is None
    assert captured.value.logs == ()
    assert "private renderer detail" not in str(captured.value)
    assert renderer.calls == 1


@pytest.mark.parametrize(
    "error",
    [
        ScoreRendererLoadError(
            "Score renderer could not load MusicXML.",
            stage="load",
            page_number=None,
            logs=(ScoreRendererLog("load", None, "load warning"),),
        ),
        ScorePageCountError(
            "Score renderer returned an invalid page count.",
            stage="page_count",
            page_number=None,
            logs=(ScoreRendererLog("page_count", None, "count warning"),),
        ),
        ScorePageRenderingError(
            "Score renderer could not render a page.",
            stage="render_page",
            page_number=1,
            logs=(ScoreRendererLog("render_page", 1, "page one warning"),),
        ),
        ScorePageRenderingError(
            "Score renderer could not render a page.",
            stage="render_page",
            page_number=2,
            logs=(
                ScoreRendererLog("render_page", 1, "page one warning"),
                ScoreRendererLog("render_page", 2, "page two warning"),
            ),
        ),
    ],
)
def test_controlled_failures_preserve_upstream_artifacts_identity_and_logs(
    error: ScoreRenderingError,
) -> None:
    original = musicxml_result(revision=8)
    midi = midi_result(original)
    before = upstream_snapshot(original, midi)

    with pytest.raises(type(error)) as captured:
        RenderMusicXmlToSvg(RaisingRenderer(error)).execute(original, ScoreRenderSettings())

    assert captured.value is error
    assert captured.value.stage == error.stage
    assert captured.value.page_number == error.page_number
    assert captured.value.logs == error.logs
    assert upstream_snapshot(original, midi) == before
    assert original.artifact.content == before[2]
    assert original.artifact.sha256 == before[3]
    assert original.original.tempo is before[5]
    assert original.original is before[6]


@pytest.mark.parametrize(
    "renderer_output",
    [
        ScoreRendererOutput(
            (ScoreRendererPage(1, b""),), (ScoreRendererLog("render_page", 1, "empty"),)
        ),
        ScoreRendererOutput(
            (ScoreRendererPage(1, b'<html xmlns="http://www.w3.org/1999/xhtml"/>'),),
            (ScoreRendererLog("render_page", 1, "wrong root"),),
        ),
    ],
)
def test_invalid_svg_failure_does_not_mutate_midi_or_musicxml(
    renderer_output: ScoreRendererOutput,
) -> None:
    original = musicxml_result(revision=9)
    midi = midi_result(original)
    before = upstream_snapshot(original, midi)

    with pytest.raises(InvalidScoreRendererOutputError) as captured:
        RenderMusicXmlToSvg(RecordingRenderer(renderer_output)).execute(
            original,
            ScoreRenderSettings(),
        )

    assert captured.value.logs
    assert upstream_snapshot(original, midi) == before


def test_constructor_rejects_non_renderer() -> None:
    with pytest.raises(TypeError):
        RenderMusicXmlToSvg(cast(Any, object()))


def test_execute_rejects_invalid_original_and_settings_before_renderer() -> None:
    renderer = RecordingRenderer(output())
    use_case = RenderMusicXmlToSvg(renderer)

    with pytest.raises(TypeError):
        use_case.execute(cast(Any, object()), ScoreRenderSettings())
    with pytest.raises(TypeError):
        use_case.execute(musicxml_result(), cast(Any, object()))

    assert renderer.calls == []


def test_architecture_and_scope_boundaries() -> None:
    domain = (ROOT / "src/saxo_ai/domain/score_rendering.py").read_text().lower()
    application = (ROOT / "src/saxo_ai/application/score_rendering.py").read_text().lower()
    adapter = (ROOT / "src/saxo_ai/infrastructure/verovio_svg.py").read_text().lower()
    routes = (ROOT / "src/saxo_ai/api/routes.py").read_text().lower()
    main = (ROOT / "src/saxo_ai/main.py").read_text().lower()

    for forbidden in (
        "hashlib",
        "elementtree",
        "xml.etree",
        "fastapi",
        "application",
        "infrastructure",
    ):
        assert forbidden not in domain
    assert "import verovio" not in domain
    assert "hashlib" in application
    assert "verovio" not in application
    assert "fastapi" not in application
    assert "import verovio" in adapter
    assert "renderToSVGFile".lower() not in adapter
    assert "tempfile" not in adapter
    assert "path(" not in adapter
    assert "pdf" not in domain + application + adapter
    assert "score_rendering" not in routes
    assert "score_rendering" not in main
    assert "sax-040" not in domain + application + adapter
