from __future__ import annotations

import hashlib
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from time import perf_counter
from typing import cast

from saxo_ai.application.transcription_errors import (
    TranscriptionCheckpointDownloadError,
    TranscriptionCheckpointMismatchError,
)
from saxo_ai.infrastructure.hf_baseline_contract import (
    CHECKPOINT_FILENAME,
    CHECKPOINT_SHA256,
    CHECKPOINT_SIZE,
    DEFAULT_CHECKPOINT_CHUNK_SIZE,
    MODEL_ID,
    MODEL_REVISION,
    CheckpointDownloader,
)


class HuggingFaceCheckpointDownloader:
    """Resolve only the fixed model, revision, and checkpoint through the HF cache."""

    def download(self, *, model_id: str, revision: str, filename: str) -> Path:
        try:
            hub = import_module("huggingface_hub")
            resolved = hub.hf_hub_download(
                repo_id=model_id,
                revision=revision,
                filename=filename,
            )
        except Exception as error:
            raise TranscriptionCheckpointDownloadError(
                "Pinned FiloSax checkpoint download failed"
            ) from error
        return Path(cast(str, resolved))


class PinnedFiloSaxCheckpointResolver:
    def __init__(
        self,
        *,
        downloader: CheckpointDownloader | None = None,
        expected_sha256: str = CHECKPOINT_SHA256,
        expected_size: int = CHECKPOINT_SIZE,
        chunk_size: int = DEFAULT_CHECKPOINT_CHUNK_SIZE,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._downloader = downloader or HuggingFaceCheckpointDownloader()
        self._expected_sha256 = expected_sha256
        self._expected_size = expected_size
        self._chunk_size = chunk_size
        self._clock = clock
        self.last_download_seconds = 0.0
        self.last_verification_seconds = 0.0
        self.verified_sha256 = expected_sha256

    def resolve(self) -> Path:
        checkpoint_path = self._download()
        actual_size, actual_sha256 = self._verify(checkpoint_path)
        if actual_sha256 != self._expected_sha256:
            raise TranscriptionCheckpointMismatchError(
                expected_sha256=self._expected_sha256,
                actual_sha256=actual_sha256,
                expected_size=self._expected_size,
                actual_size=actual_size,
            )
        self.verified_sha256 = actual_sha256
        return checkpoint_path

    def _download(self) -> Path:
        started = self._clock()
        try:
            return self._downloader.download(
                model_id=MODEL_ID,
                revision=MODEL_REVISION,
                filename=CHECKPOINT_FILENAME,
            )
        except TranscriptionCheckpointDownloadError:
            raise
        except Exception as error:
            raise TranscriptionCheckpointDownloadError(
                "Pinned FiloSax checkpoint download failed"
            ) from error
        finally:
            self.last_download_seconds = self._clock() - started

    def _verify(self, checkpoint_path: Path) -> tuple[int, str]:
        started = self._clock()
        try:
            actual_size = checkpoint_path.stat().st_size
            if actual_size != self._expected_size:
                raise TranscriptionCheckpointMismatchError(
                    expected_sha256=self._expected_sha256,
                    actual_sha256=None,
                    expected_size=self._expected_size,
                    actual_size=actual_size,
                )
            digest = hashlib.sha256()
            with checkpoint_path.open("rb") as source:
                while chunk := source.read(self._chunk_size):
                    digest.update(chunk)
            return actual_size, digest.hexdigest()
        except TranscriptionCheckpointMismatchError:
            raise
        except OSError as error:
            raise TranscriptionCheckpointDownloadError(
                "Pinned FiloSax checkpoint could not be read for verification"
            ) from error
        finally:
            self.last_verification_seconds = self._clock() - started
