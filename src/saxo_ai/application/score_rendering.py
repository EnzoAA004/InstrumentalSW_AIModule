from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, runtime_checkable
from xml.etree import ElementTree as ET

from saxo_ai.domain.musicxml_export import MusicXmlExportResult
from saxo_ai.domain.score_rendering import (
    SCORE_RENDERER_NAME,
    SVG_FILE_EXTENSION,
    SVG_MEDIA_TYPE,
    SVG_NAMESPACE,
    InvalidScoreRenderDiagnosticsError,
    InvalidScoreRenderLogEntryError,
    InvalidScoreRenderReportError,
    InvalidScoreRenderResultError,
    InvalidSvgPageArtifactError,
    ScoreRenderDiagnostics,
    ScoreRenderLogEntry,
    ScoreRenderReport,
    ScoreRenderResult,
    ScoreRenderSettings,
    SvgPageArtifact,
)


@dataclass(frozen=True, slots=True)
class ScoreRendererPage:
    page_number: int
    content: bytes


@dataclass(frozen=True, slots=True)
class ScoreRendererLog:
    stage: str
    page_number: int | None
    message: str


@dataclass(frozen=True, slots=True)
class ScoreRendererOutput:
    pages: tuple[ScoreRendererPage, ...]
    logs: tuple[ScoreRendererLog, ...]


class ScoreRenderingError(RuntimeError):
    """Stable public rendering failure with separate structured diagnostics."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        page_number: int | None,
        logs: tuple[ScoreRendererLog, ...],
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.page_number = page_number
        self.logs = logs


class ScoreRendererLoadError(ScoreRenderingError):
    """Raised when the toolkit cannot load the validated source MusicXML."""


class ScorePageCountError(ScoreRenderingError):
    """Raised when the toolkit cannot expose a positive page count."""


class ScorePageRenderingError(ScoreRenderingError):
    """Raised when one page cannot be rendered atomically."""


class InvalidScoreRendererOutputError(ValueError):
    """Raised when a renderer returns an invalid in-memory output contract."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "output",
        page_number: int | None = None,
        logs: tuple[ScoreRendererLog, ...] = (),
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.page_number = page_number
        self.logs = logs


@runtime_checkable
class ScoreRenderer(Protocol):
    def render(
        self,
        *,
        content: bytes,
        settings: ScoreRenderSettings,
    ) -> ScoreRendererOutput: ...


def _validated_logs(value: object) -> tuple[ScoreRendererLog, ...]:
    if not isinstance(value, tuple):
        raise InvalidScoreRendererOutputError("Renderer logs must be a tuple.")
    validated: list[ScoreRendererLog] = []
    for raw in value:
        if not isinstance(raw, ScoreRendererLog):
            raise InvalidScoreRendererOutputError(
                "Renderer logs must contain ScoreRendererLog values.",
                logs=tuple(validated),
            )
        try:
            ScoreRenderLogEntry(raw.stage, raw.page_number, raw.message)
        except InvalidScoreRenderLogEntryError as error:
            raise InvalidScoreRendererOutputError(
                "Renderer returned an invalid log entry.",
                stage=raw.stage if isinstance(raw.stage, str) else "output",
                page_number=raw.page_number if isinstance(raw.page_number, int) else None,
                logs=tuple(validated),
            ) from error
        validated.append(raw)
    return tuple(validated)


def _parse_svg(content: bytes, *, page_number: int, logs: tuple[ScoreRendererLog, ...]) -> None:
    if not isinstance(content, bytes) or not content:
        raise InvalidScoreRendererOutputError(
            "Renderer returned an empty or non-byte SVG page.",
            stage="render_page",
            page_number=page_number,
            logs=logs,
        )
    try:
        root = ET.fromstring(content.decode("utf-8"))
    except (UnicodeDecodeError, ET.ParseError) as error:
        raise InvalidScoreRendererOutputError(
            "Renderer returned malformed UTF-8 SVG.",
            stage="render_page",
            page_number=page_number,
            logs=logs,
        ) from error
    local_name = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
    namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
    if local_name != "svg" or namespace != SVG_NAMESPACE:
        raise InvalidScoreRendererOutputError(
            "Renderer page root must be namespaced SVG.",
            stage="render_page",
            page_number=page_number,
            logs=logs,
        )


def _build_pages(
    value: object,
    *,
    logs: tuple[ScoreRendererLog, ...],
) -> tuple[SvgPageArtifact, ...]:
    if not isinstance(value, tuple) or not value:
        raise InvalidScoreRendererOutputError(
            "Renderer must return a non-empty tuple of pages.",
            logs=logs,
        )
    if any(not isinstance(page, ScoreRendererPage) for page in value):
        raise InvalidScoreRendererOutputError(
            "Renderer pages must contain ScoreRendererPage values.",
            logs=logs,
        )

    page_count = len(value)
    pages: list[SvgPageArtifact] = []
    for expected_number, raw_page in enumerate(value, start=1):
        if (
            isinstance(raw_page.page_number, bool)
            or not isinstance(raw_page.page_number, int)
            or raw_page.page_number != expected_number
        ):
            raise InvalidScoreRendererOutputError(
                "Renderer pages must be numbered exactly from 1 to N.",
                stage="render_page",
                page_number=(
                    raw_page.page_number
                    if isinstance(raw_page.page_number, int)
                    and not isinstance(raw_page.page_number, bool)
                    else None
                ),
                logs=logs,
            )
        _parse_svg(raw_page.content, page_number=expected_number, logs=logs)
        try:
            pages.append(
                SvgPageArtifact(
                    page_number=expected_number,
                    page_count=page_count,
                    content=raw_page.content,
                    media_type=SVG_MEDIA_TYPE,
                    file_extension=SVG_FILE_EXTENSION,
                    size_bytes=len(raw_page.content),
                    sha256=sha256(raw_page.content).hexdigest(),
                )
            )
        except InvalidSvgPageArtifactError as error:
            raise InvalidScoreRendererOutputError(
                "Renderer returned an invalid SVG page artifact.",
                stage="render_page",
                page_number=expected_number,
                logs=logs,
            ) from error
    return tuple(pages)


_CONTROLLED_RENDER_ERRORS = (
    ScoreRendererLoadError,
    ScorePageCountError,
    ScorePageRenderingError,
    InvalidScoreRendererOutputError,
)


class RenderMusicXmlToSvg:
    def __init__(self, renderer: ScoreRenderer) -> None:
        if not isinstance(renderer, ScoreRenderer):
            raise TypeError("renderer must implement ScoreRenderer")
        self._renderer = renderer

    def execute(
        self,
        original: MusicXmlExportResult,
        settings: ScoreRenderSettings,
    ) -> ScoreRenderResult:
        if not isinstance(original, MusicXmlExportResult):
            raise TypeError("original must be MusicXmlExportResult")
        if not isinstance(settings, ScoreRenderSettings):
            raise TypeError("settings must be ScoreRenderSettings")

        try:
            output = self._renderer.render(
                content=original.artifact.content,
                settings=settings,
            )
        except _CONTROLLED_RENDER_ERRORS:
            raise
        except Exception as error:
            raise ScoreRenderingError(
                "Score rendering failed.",
                stage="render",
                page_number=None,
                logs=(),
            ) from error

        if not isinstance(output, ScoreRendererOutput):
            raise InvalidScoreRendererOutputError(
                "Renderer must return ScoreRendererOutput."
            )
        logs = _validated_logs(output.logs)
        pages = _build_pages(output.pages, logs=logs)
        try:
            diagnostics = ScoreRenderDiagnostics(
                renderer_name=SCORE_RENDERER_NAME,
                logs=tuple(
                    ScoreRenderLogEntry(entry.stage, entry.page_number, entry.message)
                    for entry in logs
                ),
            )
            report = ScoreRenderReport(
                settings=settings,
                page_count=len(pages),
                total_size_bytes=sum(page.size_bytes for page in pages),
                source_musicxml_sha256=original.artifact.sha256,
                source_tempo_revision=original.original.tempo.revision,
            )
            return ScoreRenderResult(
                original=original,
                pages=pages,
                diagnostics=diagnostics,
                report=report,
            )
        except (
            InvalidScoreRenderDiagnosticsError,
            InvalidScoreRenderReportError,
            InvalidScoreRenderResultError,
        ) as error:
            raise InvalidScoreRendererOutputError(
                "Renderer output is inconsistent with the source revision.",
                logs=logs,
            ) from error
