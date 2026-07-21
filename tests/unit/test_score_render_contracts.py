from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError

import pytest

from saxo_ai.domain.score_rendering import (
    SCORE_RENDER_POLICY_VERSION,
    SCORE_RENDERER_NAME,
    SVG_FILE_EXTENSION,
    SVG_MEDIA_TYPE,
    InvalidScoreRenderDiagnosticsError,
    InvalidScoreRenderLogEntryError,
    InvalidScoreRenderReportError,
    InvalidScoreRenderResultError,
    InvalidScoreRenderSettingsError,
    InvalidSvgPageArtifactError,
    ScoreRenderDiagnostics,
    ScoreRenderLogEntry,
    ScoreRenderReport,
    ScoreRenderResult,
    ScoreRenderSettings,
    SvgPageArtifact,
)
from tests.score_render_helpers import musicxml_result


def svg_bytes(page_number: int = 1) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'data-page="{page_number}" viewBox="0 0 10 10"><g/></svg>'
    ).encode()


def artifact(page_number: int = 1, page_count: int = 1) -> SvgPageArtifact:
    content = svg_bytes(page_number)
    return SvgPageArtifact(
        page_number=page_number,
        page_count=page_count,
        content=content,
        media_type=SVG_MEDIA_TYPE,
        file_extension=SVG_FILE_EXTENSION,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def test_settings_defaults_are_frozen_slotted_and_versioned() -> None:
    settings = ScoreRenderSettings()

    assert settings.page_width == 2100
    assert settings.page_height == 2970
    assert settings.scale == 100
    assert settings.policy_version == SCORE_RENDER_POLICY_VERSION == "1.0"
    assert not hasattr(settings, "__dict__")
    with pytest.raises(FrozenInstanceError):
        settings.scale = 90  # type: ignore[misc]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"page_width": 1}, 1),
        ({"page_height": 1}, 1),
        ({"scale": 1}, 1),
        ({"scale": 1000}, 1000),
    ],
)
def test_settings_accept_positive_integer_boundaries(kwargs: dict[str, object], expected: int) -> None:
    settings = ScoreRenderSettings(**kwargs)  # type: ignore[arg-type]
    field = next(iter(kwargs))
    assert getattr(settings, field) == expected


@pytest.mark.parametrize("field", ["page_width", "page_height"])
@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "1", None])
def test_page_dimensions_reject_invalid_values(field: str, value: object) -> None:
    with pytest.raises(InvalidScoreRenderSettingsError):
        ScoreRenderSettings(**{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, 1001, True, False, 1.5, "100", None])
def test_scale_rejects_invalid_values(value: object) -> None:
    with pytest.raises(InvalidScoreRenderSettingsError):
        ScoreRenderSettings(scale=value)  # type: ignore[arg-type]


def test_unknown_policy_version_is_rejected() -> None:
    with pytest.raises(InvalidScoreRenderSettingsError):
        ScoreRenderSettings(policy_version="2.0")


@pytest.mark.parametrize("stage", ["load", "page_count"])
def test_non_page_logs_require_no_page_number(stage: str) -> None:
    entry = ScoreRenderLogEntry(stage=stage, page_number=None, message="warning")
    assert entry.page_number is None


def test_render_page_log_requires_positive_page_number() -> None:
    entry = ScoreRenderLogEntry(stage="render_page", page_number=2, message="warning")
    assert entry.page_number == 2


@pytest.mark.parametrize(
    ("stage", "page_number", "message"),
    [
        ("unknown", None, "warning"),
        ("load", 1, "warning"),
        ("page_count", 1, "warning"),
        ("render_page", None, "warning"),
        ("render_page", 0, "warning"),
        ("render_page", True, "warning"),
        ("load", None, ""),
        ("load", None, 123),
    ],
)
def test_invalid_log_entries_are_rejected(stage: object, page_number: object, message: object) -> None:
    with pytest.raises(InvalidScoreRenderLogEntryError):
        ScoreRenderLogEntry(  # type: ignore[arg-type]
            stage=stage,
            page_number=page_number,
            message=message,
        )


def test_svg_artifact_validates_utf8_namespace_metadata_size_and_digest() -> None:
    page = artifact()

    assert page.page_number == page.page_count == 1
    assert page.content.decode().startswith("<svg")
    assert "http://www.w3.org/2000/svg" in page.content.decode()
    assert page.media_type == "image/svg+xml"
    assert page.file_extension == ".svg"
    assert page.size_bytes == len(page.content)
    assert page.sha256 == hashlib.sha256(page.content).hexdigest()
    assert not hasattr(page, "__dict__")


@pytest.mark.parametrize(
    "changes",
    [
        {"page_number": 0},
        {"page_number": 2},
        {"page_count": 0},
        {"content": b""},
        {"content": b"\xff"},
        {"content": b"<svg"},
        {"content": b'<html xmlns="http://www.w3.org/1999/xhtml"/>'},
        {"content": b"<svg/>"},
        {"media_type": "text/xml"},
        {"file_extension": ".xml"},
        {"size_bytes": 999},
        {"sha256": "A" * 64},
        {"sha256": "0" * 63},
        {"sha256": "z" * 64},
    ],
)
def test_invalid_svg_artifacts_are_rejected(changes: dict[str, object]) -> None:
    content = changes.get("content", svg_bytes())
    values: dict[str, object] = {
        "page_number": 1,
        "page_count": 1,
        "content": content,
        "media_type": SVG_MEDIA_TYPE,
        "file_extension": SVG_FILE_EXTENSION,
        "size_bytes": len(content) if isinstance(content, bytes) else 0,
        "sha256": hashlib.sha256(content).hexdigest() if isinstance(content, bytes) else "0" * 64,
    }
    values.update(changes)
    with pytest.raises(InvalidSvgPageArtifactError):
        SvgPageArtifact(**values)  # type: ignore[arg-type]


def test_diagnostics_are_immutable_ordered_and_renderer_specific() -> None:
    logs = (
        ScoreRenderLogEntry("load", None, "first"),
        ScoreRenderLogEntry("render_page", 1, "second"),
    )
    diagnostics = ScoreRenderDiagnostics(renderer_name=SCORE_RENDERER_NAME, logs=logs)

    assert diagnostics.renderer_name == "verovio"
    assert diagnostics.logs is logs
    assert diagnostics.logs[0].message == "first"
    assert not hasattr(diagnostics, "__dict__")


@pytest.mark.parametrize(
    ("renderer_name", "logs"),
    [("other", ()), ("", ()), ("verovio", []), ("verovio", (object(),))],
)
def test_invalid_diagnostics_are_rejected(renderer_name: object, logs: object) -> None:
    with pytest.raises(InvalidScoreRenderDiagnosticsError):
        ScoreRenderDiagnostics(renderer_name=renderer_name, logs=logs)  # type: ignore[arg-type]


def test_result_preserves_original_revision_and_complete_page_sequence() -> None:
    original = musicxml_result(revision=7)
    pages = (artifact(1, 2), artifact(2, 2))
    report = ScoreRenderReport(
        settings=ScoreRenderSettings(),
        page_count=2,
        total_size_bytes=sum(page.size_bytes for page in pages),
        source_musicxml_sha256=original.artifact.sha256,
        source_tempo_revision=7,
    )
    diagnostics = ScoreRenderDiagnostics("verovio", ())

    result = ScoreRenderResult(original, pages, diagnostics, report)

    assert result.original is original
    assert result.pages is pages
    assert tuple(page.page_number for page in result.pages) == (1, 2)
    assert result.report.source_musicxml_sha256 == original.artifact.sha256
    assert result.report.source_tempo_revision == original.original.tempo.revision == 7
    raw = result.original.original.tempo.original.original.original.original.original.original
    assert raw.model.engine_name == "filosax"
    assert raw.model.checkpoint_sha256 == "c" * 64
    assert result.original.original.tempo.original.events[0].source.event.confidence == 0.8


@pytest.mark.parametrize(
    "pages",
    [
        (),
        (artifact(2, 2), artifact(1, 2)),
        (artifact(1, 2), artifact(1, 2)),
        (artifact(1, 3), artifact(2, 3)),
    ],
)
def test_result_rejects_empty_missing_duplicate_or_out_of_order_pages(
    pages: tuple[SvgPageArtifact, ...],
) -> None:
    original = musicxml_result()
    count = len(pages) or 1
    report = ScoreRenderReport(
        ScoreRenderSettings(),
        count,
        sum(page.size_bytes for page in pages),
        original.artifact.sha256,
        original.original.tempo.revision,
    )
    with pytest.raises(InvalidScoreRenderResultError):
        ScoreRenderResult(
            original,
            pages,
            ScoreRenderDiagnostics("verovio", ()),
            report,
        )


@pytest.mark.parametrize(
    "report_factory",
    [
        lambda original, page: ScoreRenderReport(
            ScoreRenderSettings(), 2, page.size_bytes, original.artifact.sha256, 1
        ),
        lambda original, page: ScoreRenderReport(
            ScoreRenderSettings(), 1, page.size_bytes + 1, original.artifact.sha256, 1
        ),
        lambda original, page: ScoreRenderReport(
            ScoreRenderSettings(), 1, page.size_bytes, "0" * 64, 1
        ),
        lambda original, page: ScoreRenderReport(
            ScoreRenderSettings(), 1, page.size_bytes, original.artifact.sha256, 99
        ),
    ],
)
def test_result_rejects_report_inconsistencies(report_factory) -> None:
    original = musicxml_result()
    page = artifact()
    report = report_factory(original, page)
    with pytest.raises((InvalidScoreRenderReportError, InvalidScoreRenderResultError)):
        ScoreRenderResult(
            original,
            (page,),
            ScoreRenderDiagnostics("verovio", ()),
            report,
        )
