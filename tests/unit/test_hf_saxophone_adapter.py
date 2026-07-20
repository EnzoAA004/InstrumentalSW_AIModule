from __future__ import annotations

import hashlib
import math
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from saxo_ai.application.transcription_errors import (
    InvalidTranscriptionEngineOutputError,
    TranscriptionCheckpointDownloadError,
    TranscriptionCheckpointMismatchError,
    TranscriptionEngineUnavailableError,
    TranscriptionInferenceError,
    TranscriptionModelInitializationError,
)
from saxo_ai.domain.note_events import NOTE_EVENT_SCHEMA_VERSION
from saxo_ai.infrastructure.hf_saxophone import (
    BASELINE_PACKAGE_NAME,
    BASELINE_PACKAGE_VERSION,
    BEGIN_MIDI_NOTE,
    CHECKPOINT_FILENAME,
    CHECKPOINT_SHA256,
    CHECKPOINT_SIZE,
    CONFIDENCE_METHOD,
    FRAMES_PER_SECOND,
    MODEL_ID,
    MODEL_REVISION,
    PinnedFiloSaxCheckpointResolver,
    HfSaxophoneTranscriptionEngine,
)


class SpyStream:
    def __init__(self, content: bytes) -> None:
        self._stream = BytesIO(content)
        self.requests: list[int] = []

    def read(self, size: int) -> bytes:
        assert size > 0
        self.requests.append(size)
        return self._stream.read(size)


class FakeDownloader:
    def __init__(self, path: Path | None = None, error: Exception | None = None) -> None:
        self.path = path
        self.error = error
        self.calls: list[dict[str, str]] = []

    def download(self, *, model_id: str, revision: str, filename: str) -> Path:
        self.calls.append({"model_id": model_id, "revision": revision, "filename": filename})
        if self.error is not None:
            raise self.error
        assert self.path is not None
        return self.path


class FakeRuntime:
    def __init__(self, output: object = None, error: Exception | None = None) -> None:
        self.output = output
        self.error = error
        self.calls: list[tuple[Path, Path]] = []

    def transcribe(self, *, audio_path: Path, midi_path: Path) -> object:
        self.calls.append((audio_path, midi_path))
        assert audio_path.name == "canonical.wav"
        assert midi_path.name == "baseline.mid"
        assert audio_path.read_bytes()
        midi_path.write_bytes(b"temporary midi")
        if self.error is not None:
            raise self.error
        return self.output


class FakeRuntimeFactory:
    def __init__(
        self,
        runtime: FakeRuntime | None = None,
        *,
        version: str = BASELINE_PACKAGE_VERSION,
        unavailable: Exception | None = None,
        initialization_error: Exception | None = None,
    ) -> None:
        self.runtime = runtime or FakeRuntime(valid_external_output())
        self.version = version
        self.unavailable = unavailable
        self.initialization_error = initialization_error
        self.available_calls = 0
        self.create_calls: list[dict[str, object]] = []

    def ensure_available(self) -> str:
        self.available_calls += 1
        if self.unavailable is not None:
            raise self.unavailable
        return self.version

    def create(self, *, checkpoint_path: Path, settings: object) -> FakeRuntime:
        self.create_calls.append({"checkpoint_path": checkpoint_path, "settings": settings})
        if self.initialization_error is not None:
            raise self.initialization_error
        return self.runtime


def valid_external_output(
    *,
    events: list[dict[str, object]] | None = None,
    onset_matrix: object | None = None,
) -> dict[str, object]:
    if events is None:
        events = [{"onset_time": 0.0, "offset_time": 0.5, "midi_note": 69, "velocity": 100}]
    if onset_matrix is None:
        matrix = [[0.0 for _ in range(88)] for _ in range(8)]
        matrix[0][69 - BEGIN_MIDI_NOTE] = 0.73
        matrix[1][69 - BEGIN_MIDI_NOTE] = 0.92
        onset_matrix = matrix
    return {"est_note_events": events, "output_dict": {"reg_onset_output": onset_matrix}}


def make_checkpoint(directory: Path, content: bytes = b"verified checkpoint") -> tuple[Path, str]:
    path = directory / CHECKPOINT_FILENAME
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


def test_pinned_constants_are_exact() -> None:
    assert BASELINE_PACKAGE_NAME == "hf-midi-transcription"
    assert BASELINE_PACKAGE_VERSION == "0.1.1"
    assert MODD_ID not in globals()
    assert MODEL_ID == "xavriley/midi-transcription-models"
    assert MODEL_REVISION == "982ce108d7010bc3c4f36cf851caea8d4c94763d"
    assert CHECKPOINT_FILENAME == "filosax_25k.pth"
    assert CHECKPOINT_SHA256 == "448cf2c8ea6d4b77f7435f5b9a496211ea60300c5c17fa9c754da764f75f3a6a"
    assert CHECKPOINT_SIZE == 99341469
    assert FRAMES_PER_SECOND == 100
    assert BEGIN_MIDI_NOTE == 21
    assert CONFIDENCE_METHOD == "max_reg_onset_activation_pm2_frames"


def test_missing_optional_dependency_fails_before_download_or_workspace(tmp_path: Path) -> None:
    downloader = FakeDownloader(error=AssertionError("download must not run"))
    resolver = PinnedFiloSaxCheckpointResolver(downloader=downloader)
    factory = FakeRuntimeFactory(unavailable=ModuleNotFoundError("missing baseline"))
    workspace_calls: list[object] = []

    def workspace_factory() -> TemporaryDirectory[str]:
        workspace_calls.append(object())
        return TemporaryDirectory()

    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=resolver,
        runtime_factory=factory,
        temporary_directory_factory=workspace_factory,
    )
    with pytest.raises(TranscriptionEngineUnavailableError):
        engine.transcribe(SpyStream(b"wav"))
    assert downloader.calls == []
    assert workspace_calls == []


def test_checkpoint_resolver_uses_exact_identity_and_accepts_verified_content(tmp_path: Path) -> None:
    path, digest = make_checkpoint(tmp_path)
    downloader = FakeDownloader(path)
    resolver = PinnedFiloSaxCheckpointResolver(
        downloader=downloader,
        expected_sha256=digest,
        expected_size=path.stat().st_size,
        chunk_size=4,
    )
    assert resolver.resolve() == path
    assert downloader.calls == [{"model_id": MODEL_ID, "revision": MODEL_REVISION, "filename": CHECKPOINT_FILENAME}]


def test_checkpoint_mismatch_prevents_runtime_initialization_and_hides_path(tmp_path: Path) -> None:
    path, _ = make_checkpoint(tmp_path, b"one byte changed")
    resolver = PinnedFiloSaxCheckpointResolver(
        downloader=FakeDownloader(path),
        expected_sha256="0" * 64,
        expected_size=path.stat().st_size,
    )
    factory = FakeRuntimeFactory()
    engine = HfSaxophoneTranscriptionEngine(checkpoint_resolver=resolver, runtime_factory=factory)
    with pytest.raises(TranscriptionCheckpointMismatchError) as captured:
        engine.transcribe(SpyStream(b"wav"))
    assert factory.create_calls == []
    assert str(path) not in str(captured.value)


def test_download_failure_is_controlled_and_hides_external_details() -> None:
    resolver = PinnedFiloSaxCheckpointResolver(
        downloader=FakeDownloader(error=RuntimeError("/secret/cache/path unavailable"))
    )
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=resolver,
        runtime_factory=FakeRuntimeFactory(),
    )
    with pytest.raises(TranscriptionCheckpointDownloadError) as captured:
        engine.transcribe(SpyStream(b"wav"))
    assert "/secret/cache/path" not in str(captured.value)


def test_non_seekable_stream_is_copied_in_bounded_blocks_and_result_has_provenance(tmp_path: Path) -> None:
    path, digest = make_checkpoint(tmp_path)
    resolver = PinnedFiloSaxCheckpointResolver(
        downloader=FakeDownloader(path), expected_sha256=digest, expected_size=path.stat().st_size
    )
    runtime = FakeRuntime(valid_external_output())
    factory = FakeRuntimeFactory(runtime)
    source = SpyStream(b"RIFF" + b"x" * 150000)
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=resolver,
        runtime_factory=factory,
        copy_chunk_size=65536,
    )
    result = engine.transcribe(source)
    assert source.requests and all(request == 65536 for request in source.requests)
    assert result.model.engine_name == BASELINE_PACKAGE_NAME
    assert result.model.engine_version == BASELINE_PACKAGE_VERSION
    assert result.model.model_id == MODEL_ID
    assert result.model.model_revision == MODEL_REVISION
    assert result.model.checkpoint_filename == CHECKPOINT_FILENAME
    assert result.model.checkpoint_sha256 == digest
    assert result.settings.sample_rate_hz == 16000
    assert result.settings.device == "cpu"
    assert result.settings.confidence_method == CONFIDENCE_METHOD
    assert result.notes.schema_version == NOTE_EVENT_SCHEMA_VERSION
    assert len(result.notes.events) == 1
    note = result.notes.events[0]
    assert note.pitch_concert_midi == 69
    assert note.onset_seconds == 0.0
    assert note.offset_seconds == 0.5
    assert note.velocity == 100
    assert note.confidence == 0.92


def test_adapter_sorts_deterministically_but_preserves_duplicates_and_overlaps(tmp_path: Path) -> None:
    path, digest = make_checkpoint(tmp_path)
    events = [
        {"onset_time": 1.0, "offset_time": 1.5, "midi_note": 70, "velocity": 80},
        {"onset_time": 0.0, "offset_time": 0.75, "midi_note": 69, "velocity": 100},
        {"onset_time": 0.0, "offset_time": 0.75, "midi_note": 69, "velocity": 100},
        {"onset_time": 0.5, "offset_time": 1.25, "midi_note": 67, "velocity": 90},
    ]
    matrix = [[0.5 for _ in range(88)] for _ in range(160)]
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=PinnedFiloSaxCheckpointResolver(
            downloader=FakeDownloader(path), expected_sha256=digest, expected_size=path.stat().st_size
        ),
        runtime_factory=FakeRuntimeFactory(FakeRuntime(valid_external_output(events=events, onset_matrix=matrix))),
    )
    notes = engine.transcribe(SpyStream(b"wav")).notes.events
    assert [(n.onset_seconds, n.pitch_concert_midi, n.offset_seconds, n.velocity) for n in notes] == [
        (0.0, 69, 0.75, 100),
        (0.0, 69, 0.75, 100),
        (0.5, 67, 1.25, 90),
        (1.0, 70, 1.5, 80),
    ]


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
            downloader=FakeDownloader(path), expected_sha256=digest, expected_size=path.stat().st_size
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
    raw = {"onset_time": 0.0, "offset_time": 0.5, "midi_note": 69, "velocity": 100}
    raw.update(event_override)
    output = valid_external_output(events=[raw], onset_matrix=matrix_override)
    engine = HfSaxophoneTranscriptionEngine(
        checkpoint_resolver=PinnedFiloSaxCheckpointResolver(
            downloader=FakeDownloader(path), expected_sha256=digest, expected_size=path.stat().st_size
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
