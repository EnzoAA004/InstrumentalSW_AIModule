from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from saxo_ai.domain.musicxml_export import MusicXmlExportResult

SCORE_RENDER_POLICY_VERSION = "1.0"
SCORE_RENDERER_NAME = "verovio"
SVG_MEDIA_TYPE = "image/svg+xml"
SVG_FILE_EXTENSION = ".svg"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
SCORE_RENDER_DEFAULT_PAGE_WIDTH = 2100
SCORE_RENDER_DEFAULT_PAGE_HEIGHT = 2970
SCORE_RENDER_DEFAULT_SCALE = 100
SCORE_RENDER_MINIMUM_SCALE = 1
SCORE_RENDER_MAXIMUM_SCALE = 1000
SCORE_RENDER_LOG_STAGES = frozenset({"load", "page_count", "render_page"})


class InvalidScoreRenderSettingsError(ValueError):
    """Raised when score-render settings violate the versioned contract."""


class InvalidScoreRenderLogEntryError(ValueError):
    """Raised when one renderer log entry has an invalid stage or page."""


class InvalidScoreRenderDiagnosticsError(ValueError):
    """Raised when renderer diagnostics have an invalid immutable shape."""


class InvalidSvgPageArtifactError(ValueError):
    """Raised when one SVG page artifact is structurally inconsistent."""


class InvalidScoreRenderReportError(ValueError):
    """Raised when score-render metrics or source references are invalid."""


class InvalidScoreRenderResultError(ValueError):
    """Raised when rendered pages, diagnostics, report, or source disagree."""


_ErrorT = TypeVar("_ErrorT", bound=ValueError)


def _positive_integer(
    value: object,
    *,
    field_name: str,
    error_type: type[_ErrorT],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise error_type(f"{field_name} must be a positive integer")
    return value


def _non_negative_integer(
    value: object,
    *,
    field_name: str,
    error_type: type[_ErrorT],
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise error_type(f"{field_name} must be a non-negative integer")
    return value


def _digest(value: object, *, field_name: str, error_type: type[_ErrorT]) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise error_type(f"{field_name} must be 64 lowercase hexadecimal characters")
    return value


def _non_empty_string(value: object, *, field_name: str, error_type: type[_ErrorT]) -> str:
    if not isinstance(value, str) or not value:
        raise error_type(f"{field_name} must be a non-empty string")
    return value


def _validate_svg_text(content: bytes) -> None:
    if not isinstance(content, bytes) or not content:
        raise InvalidSvgPageArtifactError("content must be non-empty bytes")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidSvgPageArtifactError("content must be valid UTF-8") from error

    document = text.lstrip()
    if document.startswith("<?xml"):
        declaration_end = document.find("?>")
        if declaration_end < 0:
            raise InvalidSvgPageArtifactError("SVG XML declaration is malformed")
        document = document[declaration_end + 2 :].lstrip()
    if not document.startswith("<") or document.startswith(("</", "<!", "<?")):
        raise InvalidSvgPageArtifactError("content root must be SVG")

    opening_end = document.find(">")
    if opening_end < 0:
        raise InvalidSvgPageArtifactError("SVG root opening tag is malformed")
    opening = document[1:opening_end]
    root_name = opening.split(maxsplit=1)[0].rstrip("/")
    local_name = root_name.rsplit(":", 1)[-1]
    if local_name != "svg":
        raise InvalidSvgPageArtifactError("content root local-name must be svg")
    if SVG_NAMESPACE not in opening:
        raise InvalidSvgPageArtifactError("SVG root must declare the SVG namespace")

    if opening.rstrip().endswith("/"):
        trailing = document[opening_end + 1 :].strip()
        if trailing:
            raise InvalidSvgPageArtifactError("self-closing SVG root cannot have trailing content")
        return

    closing = f"</{root_name}>"
    if not document.rstrip().endswith(closing):
        raise InvalidSvgPageArtifactError("SVG root closing tag is missing or inconsistent")


@dataclass(frozen=True, slots=True)
class ScoreRenderSettings:
    page_width: int = SCORE_RENDER_DEFAULT_PAGE_WIDTH
    page_height: int = SCORE_RENDER_DEFAULT_PAGE_HEIGHT
    scale: int = SCORE_RENDER_DEFAULT_SCALE
    policy_version: str = SCORE_RENDER_POLICY_VERSION

    def __post_init__(self) -> None:
        page_width = _positive_integer(
            self.page_width,
            field_name="page_width",
            error_type=InvalidScoreRenderSettingsError,
        )
        page_height = _positive_integer(
            self.page_height,
            field_name="page_height",
            error_type=InvalidScoreRenderSettingsError,
        )
        scale = _positive_integer(
            self.scale,
            field_name="scale",
            error_type=InvalidScoreRenderSettingsError,
        )
        if not SCORE_RENDER_MINIMUM_SCALE <= scale <= SCORE_RENDER_MAXIMUM_SCALE:
            raise InvalidScoreRenderSettingsError(
                f"scale must be between {SCORE_RENDER_MINIMUM_SCALE} and "
                f"{SCORE_RENDER_MAXIMUM_SCALE}"
            )
        if self.policy_version != SCORE_RENDER_POLICY_VERSION:
            raise InvalidScoreRenderSettingsError(
                f"policy_version must be {SCORE_RENDER_POLICY_VERSION!r}"
            )
        object.__setattr__(self, "page_width", page_width)
        object.__setattr__(self, "page_height", page_height)
        object.__setattr__(self, "scale", scale)


@dataclass(frozen=True, slots=True)
class ScoreRenderLogEntry:
    stage: str
    page_number: int | None
    message: str

    def __post_init__(self) -> None:
        if self.stage not in SCORE_RENDER_LOG_STAGES:
            raise InvalidScoreRenderLogEntryError("stage is not supported")
        _non_empty_string(
            self.message,
            field_name="message",
            error_type=InvalidScoreRenderLogEntryError,
        )
        if self.stage == "render_page":
            _positive_integer(
                self.page_number,
                field_name="page_number",
                error_type=InvalidScoreRenderLogEntryError,
            )
        elif self.page_number is not None:
            raise InvalidScoreRenderLogEntryError(
                "page_number must be None for load and page_count logs"
            )


@dataclass(frozen=True, slots=True)
class ScoreRenderDiagnostics:
    renderer_name: str
    logs: tuple[ScoreRenderLogEntry, ...]

    def __post_init__(self) -> None:
        if self.renderer_name != SCORE_RENDERER_NAME:
            raise InvalidScoreRenderDiagnosticsError(
                f"renderer_name must be {SCORE_RENDERER_NAME!r}"
            )
        if not isinstance(self.logs, tuple) or any(
            not isinstance(entry, ScoreRenderLogEntry) for entry in self.logs
        ):
            raise InvalidScoreRenderDiagnosticsError(
                "logs must be a tuple of ScoreRenderLogEntry values"
            )


@dataclass(frozen=True, slots=True)
class SvgPageArtifact:
    page_number: int
    page_count: int
    content: bytes
    media_type: str
    file_extension: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        page_number = _positive_integer(
            self.page_number,
            field_name="page_number",
            error_type=InvalidSvgPageArtifactError,
        )
        page_count = _positive_integer(
            self.page_count,
            field_name="page_count",
            error_type=InvalidSvgPageArtifactError,
        )
        if page_number > page_count:
            raise InvalidSvgPageArtifactError("page_number cannot exceed page_count")
        _validate_svg_text(self.content)
        if self.media_type != SVG_MEDIA_TYPE:
            raise InvalidSvgPageArtifactError(f"media_type must be {SVG_MEDIA_TYPE!r}")
        if self.file_extension != SVG_FILE_EXTENSION:
            raise InvalidSvgPageArtifactError(
                f"file_extension must be {SVG_FILE_EXTENSION!r}"
            )
        size = _non_negative_integer(
            self.size_bytes,
            field_name="size_bytes",
            error_type=InvalidSvgPageArtifactError,
        )
        if size != len(self.content):
            raise InvalidSvgPageArtifactError("size_bytes must equal content length")
        _digest(
            self.sha256,
            field_name="sha256",
            error_type=InvalidSvgPageArtifactError,
        )
        object.__setattr__(self, "page_number", page_number)
        object.__setattr__(self, "page_count", page_count)
        object.__setattr__(self, "size_bytes", size)


@dataclass(frozen=True, slots=True)
class ScoreRenderReport:
    settings: ScoreRenderSettings
    page_count: int
    total_size_bytes: int
    source_musicxml_sha256: str
    source_tempo_revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.settings, ScoreRenderSettings):
            raise InvalidScoreRenderReportError("settings must be ScoreRenderSettings")
        page_count = _positive_integer(
            self.page_count,
            field_name="page_count",
            error_type=InvalidScoreRenderReportError,
        )
        total_size = _non_negative_integer(
            self.total_size_bytes,
            field_name="total_size_bytes",
            error_type=InvalidScoreRenderReportError,
        )
        _digest(
            self.source_musicxml_sha256,
            field_name="source_musicxml_sha256",
            error_type=InvalidScoreRenderReportError,
        )
        source_revision = _positive_integer(
            self.source_tempo_revision,
            field_name="source_tempo_revision",
            error_type=InvalidScoreRenderReportError,
        )
        object.__setattr__(self, "page_count", page_count)
        object.__setattr__(self, "total_size_bytes", total_size)
        object.__setattr__(self, "source_tempo_revision", source_revision)


@dataclass(frozen=True, slots=True)
class ScoreRenderResult:
    original: MusicXmlExportResult
    pages: tuple[SvgPageArtifact, ...]
    diagnostics: ScoreRenderDiagnostics
    report: ScoreRenderReport

    def __post_init__(self) -> None:
        if not isinstance(self.original, MusicXmlExportResult):
            raise InvalidScoreRenderResultError("original must be MusicXmlExportResult")
        if not isinstance(self.pages, tuple) or not self.pages:
            raise InvalidScoreRenderResultError("pages must be a non-empty tuple")
        if any(not isinstance(page, SvgPageArtifact) for page in self.pages):
            raise InvalidScoreRenderResultError("pages must contain SvgPageArtifact values")
        if not isinstance(self.diagnostics, ScoreRenderDiagnostics):
            raise InvalidScoreRenderResultError(
                "diagnostics must be ScoreRenderDiagnostics"
            )
        if not isinstance(self.report, ScoreRenderReport):
            raise InvalidScoreRenderResultError("report must be ScoreRenderReport")

        expected_count = len(self.pages)
        expected_numbers = tuple(range(1, expected_count + 1))
        actual_numbers = tuple(page.page_number for page in self.pages)
        if actual_numbers != expected_numbers:
            raise InvalidScoreRenderResultError("pages must be numbered exactly from 1 to N")
        if any(page.page_count != expected_count for page in self.pages):
            raise InvalidScoreRenderResultError(
                "every page_count must equal the result page count"
            )
        if self.report.page_count != expected_count:
            raise InvalidScoreRenderResultError("report page_count must match pages")
        if self.report.total_size_bytes != sum(page.size_bytes for page in self.pages):
            raise InvalidScoreRenderResultError("report total size must match page sizes")
        if self.report.source_musicxml_sha256 != self.original.artifact.sha256:
            raise InvalidScoreRenderResultError(
                "report source MusicXML digest must match the original artifact"
            )
        if self.report.source_tempo_revision != self.original.original.tempo.revision:
            raise InvalidScoreRenderResultError(
                "report source tempo revision must match the original result"
            )
