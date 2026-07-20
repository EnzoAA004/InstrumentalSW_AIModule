from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from saxo_ai.infrastructure.hf_saxophone import (
    BASELINE_PACKAGE_VERSION,
    BEGIN_MIDI_NOTE,
    CHECKPOINT_FILENAME,
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
        events = [
            {
                "onset_time": 0.0,
                "offset_time": 0.5,
                "midi_note": 69,
                "velocity": 100,
            }
        ]
    if onset_matrix is None:
        matrix = [[0.0 for _ in range(88)] for _ in range(8)]
        matrix[0][69 - BEGIN_MIDI_NOTE] = 0.73
        matrix[1][69 - BEGIN_MIDI_NOTE] = 0.92
        onset_matrix = matrix
    return {"est_note_events": events, "output_dict": {"reg_onset_output": onset_matrix}}


def make_checkpoint(
    directory: Path,
    content: bytes = b"verified checkpoint",
) -> tuple[Path, str]:
    path = directory / CHECKPOINT_FILENAME
    path.write_bytes(content)
    return path, hashlib.sha256(content).hexdigest()


class WorkspaceTracker:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def __call__(self) -> TemporaryDirectory[str]:
        directory = TemporaryDirectory(prefix="saxo-test-baseline-")
        self.paths.append(Path(directory.name))
        return directory

    def assert_cleaned(self) -> None:
        assert self.paths
        assert all(not path.exists() for path in self.paths)
