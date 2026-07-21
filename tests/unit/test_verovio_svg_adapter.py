from __future__ import annotations

from collections.abc import Callable

import pytest
import verovio

from saxo_ai.application.score_rendering import (
    ScorePageCountError,
    ScorePageRenderingError,
    ScoreRendererLoadError,
)
from saxo_ai.domain.score_rendering import ScoreRenderSettings
from saxo_ai.infrastructure.verovio_svg import VerovioSvgScoreRenderer

SVG_ONE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><g/></svg>'
SVG_TWO = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><g/></svg>'
MUSICXML = b'<?xml version="1.0" encoding="utf-8"?><score-partwise version="4.0"/>'


class FakeToolkit:
    def __init__(
        self,
        *,
        load_result: object = True,
        page_count: object = 2,
        rendered: dict[int, object] | None = None,
        log_values: tuple[object, ...] = ("", "", "", ""),
        load_error: Exception | None = None,
        page_count_error: Exception | None = None,
        render_errors: dict[int, Exception] | None = None,
    ) -> None:
        self.load_result = load_result
        self.page_count = page_count
        self.rendered = rendered or {1: SVG_ONE, 2: SVG_TWO}
        self.log_values = list(log_values)
        self.load_error = load_error
        self.page_count_error = page_count_error
        self.render_errors = render_errors or {}
        self.options: dict[str, object] | None = None
        self.loaded_text: str | None = None
        self.render_calls: list[tuple[int, bool]] = []

    def setOptions(self, options: dict[str, object]) -> None:
        self.options = options

    def loadData(self, text: str) -> object:
        self.loaded_text = text
        if self.load_error is not None:
            raise self.load_error
        return self.load_result

    def getPageCount(self) -> object:
        if self.page_count_error is not None:
            raise self.page_count_error
        return self.page_count

    def renderToSVG(self, page_number: int, xml_declaration: bool) -> object:
        self.render_calls.append((page_number, xml_declaration))
        error = self.render_errors.get(page_number)
        if error is not None:
            raise error
        return self.rendered[page_number]

    def getLog(self) -> object:
        if not self.log_values:
            return ""
        return self.log_values.pop(0)


def configure_fake(
    monkeypatch: pytest.MonkeyPatch,
    toolkit_factory: Callable[[], FakeToolkit],
) -> tuple[list[bool], list[object]]:
    buffered: list[bool] = []
    levels: list[object] = []
    monkeypatch.setattr(
        verovio,
        "enableLogToBuffer",
        lambda enabled: buffered.append(enabled),
        raising=False,
    )
    monkeypatch.setattr(
        verovio,
        "enableLog",
        lambda level: levels.append(level),
    )
    monkeypatch.setattr(verovio, "toolkit", toolkit_factory)
    return buffered, levels


def test_adapter_uses_exact_options_renders_all_pages_and_preserves_log_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toolkit = FakeToolkit(
        log_values=(
            "load warning\n",
            "load warning\ncount warning\n",
            "load warning\ncount warning\npage one warning\n",
            "load warning\ncount warning\npage one warning\npage two warning\n",
        )
    )
    buffered, levels = configure_fake(monkeypatch, lambda: toolkit)
    settings = ScoreRenderSettings(page_width=800, page_height=1000, scale=75)

    output = VerovioSvgScoreRenderer().render(content=MUSICXML, settings=settings)

    assert buffered == [True]
    assert levels == [verovio.LOG_WARNING]
    assert toolkit.options == {
        "inputFrom": "xml",
        "pageWidth": 800,
        "pageHeight": 1000,
        "scale": 75,
        "svgViewBox": True,
        "xmlIdChecksum": True,
    }
    assert toolkit.options is not None
    assert "xmlIdSeed" not in toolkit.options
    assert toolkit.loaded_text == MUSICXML.decode("utf-8")
    assert toolkit.render_calls == [(1, True), (2, True)]
    assert tuple(page.page_number for page in output.pages) == (1, 2)
    assert tuple(page.content for page in output.pages) == (
        SVG_ONE.encode("utf-8"),
        SVG_TWO.encode("utf-8"),
    )
    assert [(entry.stage, entry.page_number, entry.message) for entry in output.logs] == [
        ("load", None, "load warning\n"),
        ("page_count", None, "count warning\n"),
        ("render_page", 1, "page one warning\n"),
        ("render_page", 2, "page two warning\n"),
    ]


def test_every_render_uses_a_new_toolkit_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    toolkits = [
        FakeToolkit(page_count=1, rendered={1: SVG_ONE}, log_values=("", "", "")),
        FakeToolkit(page_count=1, rendered={1: SVG_ONE}, log_values=("", "", "")),
    ]
    configure_fake(monkeypatch, lambda: toolkits.pop(0))
    renderer = VerovioSvgScoreRenderer()

    first = renderer.render(content=MUSICXML, settings=ScoreRenderSettings())
    second = renderer.render(content=MUSICXML, settings=ScoreRenderSettings())

    assert first == second
    assert toolkits == []


@pytest.mark.parametrize(
    "toolkit",
    [
        FakeToolkit(load_result=False, log_values=("load rejected",)),
        FakeToolkit(load_error=LookupError("private load"), log_values=()),
    ],
)
def test_load_failures_are_controlled_and_keep_available_logs(
    monkeypatch: pytest.MonkeyPatch,
    toolkit: FakeToolkit,
) -> None:
    configure_fake(monkeypatch, lambda: toolkit)

    with pytest.raises(ScoreRendererLoadError) as captured:
        VerovioSvgScoreRenderer().render(content=MUSICXML, settings=ScoreRenderSettings())

    assert captured.value.stage == "load"
    assert captured.value.page_number is None
    if toolkit.load_result is False:
        assert captured.value.logs[0].message == "load rejected"
    if toolkit.load_error is not None:
        assert captured.value.__cause__ is toolkit.load_error
    assert "private load" not in str(captured.value)


@pytest.mark.parametrize("page_count", [0, -1, True, "2", None])
def test_invalid_page_counts_are_rejected_with_stage_logs(
    monkeypatch: pytest.MonkeyPatch,
    page_count: object,
) -> None:
    toolkit = FakeToolkit(
        page_count=page_count,
        log_values=("", "count warning", ""),
    )
    configure_fake(monkeypatch, lambda: toolkit)

    with pytest.raises(ScorePageCountError) as captured:
        VerovioSvgScoreRenderer().render(content=MUSICXML, settings=ScoreRenderSettings())

    assert captured.value.stage == "page_count"
    assert captured.value.page_number is None
    assert captured.value.logs[0].message == "count warning"
    assert toolkit.render_calls == []


def test_page_count_exception_keeps_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    error = LookupError("private count")
    toolkit = FakeToolkit(
        page_count_error=error,
        log_values=("",),
    )
    configure_fake(monkeypatch, lambda: toolkit)

    with pytest.raises(ScorePageCountError) as captured:
        VerovioSvgScoreRenderer().render(content=MUSICXML, settings=ScoreRenderSettings())

    assert captured.value.__cause__ is error
    assert "private count" not in str(captured.value)


@pytest.mark.parametrize("rendered", ["", None, b"not a string"])
def test_empty_or_wrong_type_page_is_rejected_atomically(
    monkeypatch: pytest.MonkeyPatch,
    rendered: object,
) -> None:
    toolkit = FakeToolkit(
        page_count=2,
        rendered={1: SVG_ONE, 2: rendered},
        log_values=("", "", "page one", "page two"),
    )
    configure_fake(monkeypatch, lambda: toolkit)

    with pytest.raises(ScorePageRenderingError) as captured:
        VerovioSvgScoreRenderer().render(content=MUSICXML, settings=ScoreRenderSettings())

    assert captured.value.stage == "render_page"
    assert captured.value.page_number == 2
    assert [entry.message for entry in captured.value.logs] == ["page one", "page two"]
    assert toolkit.render_calls == [(1, True), (2, True)]


def test_intermediate_page_exception_returns_no_partial_success_and_keeps_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = RuntimeError("private page")
    toolkit = FakeToolkit(
        page_count=3,
        rendered={1: SVG_ONE, 2: SVG_TWO, 3: SVG_ONE},
        render_errors={2: error},
        log_values=("", "", "page one"),
    )
    configure_fake(monkeypatch, lambda: toolkit)

    with pytest.raises(ScorePageRenderingError) as captured:
        VerovioSvgScoreRenderer().render(content=MUSICXML, settings=ScoreRenderSettings())

    assert captured.value.page_number == 2
    assert captured.value.__cause__ is error
    assert captured.value.logs[0].page_number == 1
    assert toolkit.render_calls == [(1, True), (2, True)]
    assert "private page" not in str(captured.value)


@pytest.mark.parametrize("content", [b"", b"\xff", "not bytes"])
def test_invalid_input_is_rejected_before_toolkit_creation(
    monkeypatch: pytest.MonkeyPatch,
    content: object,
) -> None:
    created = 0

    def factory() -> FakeToolkit:
        nonlocal created
        created += 1
        return FakeToolkit()

    configure_fake(monkeypatch, factory)

    with pytest.raises(ScoreRendererLoadError):
        VerovioSvgScoreRenderer().render(
            content=content,  # type: ignore[arg-type]
            settings=ScoreRenderSettings(),
        )

    assert created == 0
