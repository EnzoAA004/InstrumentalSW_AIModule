from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from saxo_ai.application.transcription_errors import (
    TranscriptionCheckpointDownloadError,
    TranscriptionCheckpointMismatchError,
    TranscriptionEngineUnavailableError,
)
from saxo_ai.infrastructure.hf_saxophone import (
    CHECKPOINT_FILENAME,
    MODEL_ID,
    MODEL_REVISION,
    HfSaxophoneTranscriptionEngine,
    PinnedFiloSaxCheckpointResolver,
)
from tests.unit.hf_saxophone_fakes import (
    FakeDownloader,
    FakeRuntimeFactory,
    SpyStream,
    make_checkpoint,
)


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


def test_checkpoint_resolver_uses_exact_identity_and_accepts_verified_content(
    tmp_path: Path,
) -> None:
    path, digest = make_checkpoint(tmp_path)
    downloader = FakeDownloader(path)
    resolver = PinnedFiloSaxCheckpointResolver(
        downloader=downloader,
        expected_sha256=digest,
        expected_size=path.stat().st_size,
        chunk_size=4,
    )
    assert resolver.resolve() == path
    assert downloader.calls == [
        {"model_id": MODEL_ID, "revision": MODEL_REVISION, "filename": CHECKPOINT_FILENAME}
    ]


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
