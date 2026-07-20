from __future__ import annotations

import math
from pathlib import Path

import pytest

from saxo_ai.application.transcription_errors import (
    InvalidTranscriptionEngineOutputError,
    TranscriptionCheckpointDownloadError,
    TranscriptionCheckpointMismatchError,
    TranscriptionEngineUnavailableError,
    TranscriptionInferenceError,
    TranscriptionModelInitializationError,
)
from saxo_ai.infrastructure.hf_saxophone import (
    HfSaxophoneTranscriptionEngine,
    PinnedFiloSaxCheckpointResolver,
)
from tests.unit.hf_saxophone_fakes import (
    FakeDownloader,
    FakeRuntime,
    FakeRuntimeFactory,
    SpyStream,
    WorkspaceTracker,
    make_checkpoint,
    valid_external_output,
)


@pytest.mark.parametrize(
    "output",
    [
        {},
        {"est_note_events": []},
        {"output_dict": {"reg_onset_output": [[0.1]]}},
        {"est_note_events": [], "output_dict": {}},
        {"est_note_events": [], "output_dict": {"reg_onset_output": [0.1, 0.2]}},
        {"est_note_events": [object()], "output_dict": {"reg_onset_output": [[0.1] * 88]}},
        {"est_note_events": [{}], "output_dict": {"reg_onset_output": [[0.1] * 88]}},
    ],
)
def test_invalid_external_structures_raise_controlled_error(output: object, tmp_path: Path) -> None:
    path, digest = make_checkpoint(tmp_path)
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=PinnedFiloSaxCheckpointResolver(
            downloader=FakeDownloader(path),
            expected_sha256=digest,
            expected_size=path.stat().st_size,
        ),
        runtime_factory=FakeRuntimeFactory(FakeRuntime(output)),
    )
    with pytest.raises(InvalidTranscriptionEngineOutputError):
        engine.transcribe(SpyStream(b"wav"))


@pytest.mark.parametrize(
    ("event_override", "matrix_override"),
    [
        ({"midi_note": 120}, None),
        ({"velocity": 128}, None),
        ({"offset_time": 0.0}, None),
        ({"onset_time": -0.1}, None),
        ({}, [[math.nan for _ in range(88)] for _ in range(8)]),
    ],
)
def test_invalid_events_and_confidence_include_event_index(
    event_override: dict[str, object],
    matrix_override: object | None,
    tmp_path: Path,
) -> None:
    path, digest = make_checkpoint(tmp_path)
    raw: dict[str, object] = {
        "onset_time": 0.0,
        "offset_time": 0.5,
        "midi_note": 69,
        "velocity": 100,
    }
    raw.update(event_override)
    output = valid_external_output(events=[raw], onset_matrix=matrix_override)
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=PinnedFiloSaxCheckpointResolver(
            downloader=FakeDownloader(path),
            expected_sha256=digest,
            expected_size=path.stat().st_size,
        ),
        runtime_factory=FakeRuntimeFactory(FakeRuntime(output)),
    )
    with pytest.raises(InvalidTranscriptionEngineOutputError, match="index 0") as captured:
        engine.transcribe(SpyStream(b"wav"))
    assert captured.value.event_index == 0


def test_initialization_and_inference_failures_are_distinct(tmp_path: Path) -> None:
    path, digest = make_checkpoint(tmp_path)
    resolver = PinnedFiloSaxCheckpointResolver(
        downloader=FakeDownloader(path), expected_sha256=digest, expected_size=path.stat().st_size
    )
    init_engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=resolver,
        runtime_factory=FakeRuntimeFactory(initialization_error=RuntimeError("init")),
    )
    with pytest.raises(TranscriptionModelInitializationError):
        init_engine.transcribe(SpyStream(b"wav"))

    infer_engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=resolver,
        runtime_factory=FakeRuntimeFactory(FakeRuntime(error=RuntimeError("infer"))),
    )
    with pytest.raises(TranscriptionInferenceError):
        infer_engine.transcribe(SpyStream(b"wav"))


@pytest.mark.parametrize("stage", ["download", "checksum", "initialization", "inference", "output"])
def test_workspace_is_cleaned_after_each_controlled_failure(stage: str, tmp_path: Path) -> None:
    path, digest = make_checkpoint(tmp_path)
    tracker = WorkspaceTracker()
    downloader: FakeDownloader = FakeDownloader(path)
    expected_sha256 = digest
    factory = FakeRuntimeFactory()
    if stage == "download":
        downloader = FakeDownloader(error=RuntimeError("download"))
    elif stage == "checksum":
        expected_sha256 = "0" * 64
    elif stage == "initialization":
        factory = FakeRuntimeFactory(initialization_error=RuntimeError("init"))
    elif stage == "inference":
        factory = FakeRuntimeFactory(FakeRuntime(error=RuntimeError("infer")))
    elif stage == "output":
        factory = FakeRuntimeFactory(FakeRuntime({}))

    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=PinnedFiloSaxCheckpointResolver(
            downloader=downloader,
            expected_sha256=expected_sha256,
            expected_size=path.stat().st_size,
        ),
        runtime_factory=factory,
        temporary_directory_factory=tracker,
    )
    with pytest.raises(
        (
            TranscriptionCheckpointDownloadError,
            TranscriptionCheckpointMismatchError,
            TranscriptionModelInitializationError,
            TranscriptionInferenceError,
            InvalidTranscriptionEngineOutputError,
        )
    ):
        engine.transcribe(SpyStream(b"wav"))
    tracker.assert_cleaned()


def test_wrong_optional_package_version_is_rejected_before_download() -> None:
    downloader = FakeDownloader(error=AssertionError("download must not run"))
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=PinnedFiloSaxCheckpointResolver(downloader=downloader),
        runtime_factory=FakeRuntimeFactory(version="0.2.0"),
    )
    with pytest.raises(TranscriptionEngineUnavailableError, match=r"0\.1\.1"):
        engine.transcribe(SpyStream(b"wav"))
    assert downloader.calls == []
