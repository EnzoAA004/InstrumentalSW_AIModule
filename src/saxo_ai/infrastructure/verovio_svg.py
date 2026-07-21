from __future__ import annotations

from typing import Any

import verovio

from saxo_ai.application.score_rendering import (
    ScorePageCountError,
    ScorePageRenderingError,
    ScoreRendererLoadError,
    ScoreRendererLog,
    ScoreRendererOutput,
    ScoreRendererPage,
)
from saxo_ai.domain.score_rendering import ScoreRenderSettings


def _new_log_content(current: object, previous: str) -> tuple[str, str]:
    if not isinstance(current, str):
        return previous, ""
    if previous and current.startswith(previous):
        message = current[len(previous) :]
    elif current == previous:
        message = ""
    else:
        message = current
    return current, message


def _capture_log(
    toolkit: Any,
    *,
    stage: str,
    page_number: int | None,
    previous: str,
    logs: list[ScoreRendererLog],
) -> str:
    current = toolkit.getLog()
    updated, message = _new_log_content(current, previous)
    if message:
        logs.append(ScoreRendererLog(stage, page_number, message))
    return updated


def _toolkit(settings: ScoreRenderSettings) -> Any:
    enable_log_to_buffer = getattr(verovio, "enableLogToBuffer", None)
    if callable(enable_log_to_buffer):
        enable_log_to_buffer(True)
    verovio.enableLog(verovio.LOG_WARNING)
    toolkit = verovio.toolkit()
    toolkit.setOptions(
        {
            "inputFrom": "xml",
            "pageWidth": settings.page_width,
            "pageHeight": settings.page_height,
            "scale": settings.scale,
            "svgViewBox": True,
            "xmlIdChecksum": True,
        }
    )
    return toolkit


class VerovioSvgScoreRenderer:
    def render(
        self,
        *,
        content: bytes,
        settings: ScoreRenderSettings,
    ) -> ScoreRendererOutput:
        if not isinstance(content, bytes) or not content:
            raise ScoreRendererLoadError(
                "Score renderer requires non-empty MusicXML bytes.",
                stage="load",
                page_number=None,
                logs=(),
            )
        if not isinstance(settings, ScoreRenderSettings):
            raise TypeError("settings must be ScoreRenderSettings")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ScoreRendererLoadError(
                "Score renderer requires UTF-8 MusicXML.",
                stage="load",
                page_number=None,
                logs=(),
            ) from error

        logs: list[ScoreRendererLog] = []
        previous_log = ""
        try:
            toolkit = _toolkit(settings)
            loaded = bool(toolkit.loadData(text))
            previous_log = _capture_log(
                toolkit,
                stage="load",
                page_number=None,
                previous=previous_log,
                logs=logs,
            )
        except ScoreRendererLoadError:
            raise
        except Exception as error:
            raise ScoreRendererLoadError(
                "Score renderer could not load MusicXML.",
                stage="load",
                page_number=None,
                logs=tuple(logs),
            ) from error
        if not loaded:
            raise ScoreRendererLoadError(
                "Score renderer rejected MusicXML.",
                stage="load",
                page_number=None,
                logs=tuple(logs),
            )

        try:
            page_count = toolkit.getPageCount()
            previous_log = _capture_log(
                toolkit,
                stage="page_count",
                page_number=None,
                previous=previous_log,
                logs=logs,
            )
        except Exception as error:
            raise ScorePageCountError(
                "Score renderer could not determine page count.",
                stage="page_count",
                page_number=None,
                logs=tuple(logs),
            ) from error
        if isinstance(page_count, bool) or not isinstance(page_count, int) or page_count <= 0:
            raise ScorePageCountError(
                "Score renderer returned an invalid page count.",
                stage="page_count",
                page_number=None,
                logs=tuple(logs),
            )

        pages: list[ScoreRendererPage] = []
        for page_number in range(1, page_count + 1):
            try:
                rendered = toolkit.renderToSVG(page_number, True)
                previous_log = _capture_log(
                    toolkit,
                    stage="render_page",
                    page_number=page_number,
                    previous=previous_log,
                    logs=logs,
                )
            except Exception as error:
                raise ScorePageRenderingError(
                    "Score renderer could not render a page.",
                    stage="render_page",
                    page_number=page_number,
                    logs=tuple(logs),
                ) from error
            if not isinstance(rendered, str) or not rendered:
                raise ScorePageRenderingError(
                    "Score renderer returned an empty page.",
                    stage="render_page",
                    page_number=page_number,
                    logs=tuple(logs),
                )
            pages.append(ScoreRendererPage(page_number, rendered.encode("utf-8")))

        return ScoreRendererOutput(pages=tuple(pages), logs=tuple(logs))
