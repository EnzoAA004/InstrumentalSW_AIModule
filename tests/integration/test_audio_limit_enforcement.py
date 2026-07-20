from __future__ import annotations

import hashlib
import math
import os
import shutil
import struct
import subprocess
import wave
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory as RealTemporaryDirectory
from types import TracebackType
from typing import ClassVar
from uuid import uuid4

import pytest

from saxo_ai.application.audio_validation import ValidateTranscriptionAudio
from saxo_ai.application.errors import TranscriptionAudioValidationError
from saxo_ai.domain.audio import AudioProcessingLimits, CanonicalAudioSettings
from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
    TranscriptionJob,
)
from saxo_ai.infrastructure.ffmpeg import FfmpegCanonicalAudioConverter
from saxo_ai.infrastructure.repositories import InMemoryTranscriptionJobRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def require_ffmpeg() -> Iterator[None]:
    if shutil.which("ffmpeg") is None:
        if os.environ.get("SAXO_REQUIRE_FFMPEG") == "1":
            pytest.fail("SAXO_REQUIRE_FFMPEG=1 but ffmpeg is not installed")
        pytest.skip("ffmpeg is not installed; audio-limit integration tests skipped")
    yield


class TrackingTemporaryDirectory:
    paths: ClassVar[list[Path]] = []

    def __init__(self, *, prefix: str | None = None) -> None:
        self._delegate = RealTemporaryDirectory(prefix=prefix)

    def __enter__(self) -> str:
        path = str(self._delegate.__enter__())
        self.paths.append(Path(path))
        return path

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._delegate.__exit__(exc_type, exc, traceback)


def wav_bytes(*, sample_rate: int, frame_count: int) -> bytes:
    destination = BytesIO()
    with wave.open(destination, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            sample = round(8000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        output.writeframes(frames)
    return destination.getvalue()


def mp3_bytes_from_wav(content: bytes, tmp_path: Path) -> bytes:
    source = tmp_path / "source.wav"
    output = tmp_path / "source.mp3"
    source.write_bytes(content)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return output.read_bytes()


def make_job(filename: str, content: bytes) -> TranscriptionJob:
    return TranscriptionJob(
        job_id=uuid4(),
        status=JobStatus.UPLOADED,
        filename=filename,
        size_bytes=len(content),
        audio_sha256=hashlib.sha256(content).hexdigest(),
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )


def run_validation(
    *,
    filename: str,
    content: bytes,
    limits: AudioProcessingLimits,
) -> tuple[InMemoryTranscriptionJobRepository, TranscriptionJob, BytesIO, object]:
    repository = InMemoryTranscriptionJobRepository()
    job = make_job(filename, content)
    repository.save(job)
    destination = BytesIO()
    result = ValidateTranscriptionAudio(
        repository,
        FfmpegCanonicalAudioConverter(limits=limits),
    ).execute(
        job_id=job.job_id,
        source=BytesIO(content),
        destination=destination,
        settings=CanonicalAudioSettings(),
    )
    return repository, job, destination, result


def test_real_wav_exact_duration_limit_is_accepted() -> None:
    content = wav_bytes(sample_rate=16_000, frame_count=16_000)
    repository, job, destination, result = run_validation(
        filename="exact.wav",
        content=content,
        limits=AudioProcessingLimits(max_duration_seconds=1.0),
    )
    assert repository.get(job.job_id) == job
    assert job.status is JobStatus.UPLOADED
    assert job.failure_code is None
    assert destination.getvalue().startswith(b"RIFF")
    assert result.metadata.duration_seconds == 1.0  # type: ignore[attr-defined]


def test_real_wav_one_frame_over_duration_limit_fails_without_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from saxo_ai.infrastructure import ffmpeg as ffmpeg_module

    TrackingTemporaryDirectory.paths.clear()
    monkeypatch.setattr(ffmpeg_module, "TemporaryDirectory", TrackingTemporaryDirectory)
    content = wav_bytes(sample_rate=16_000, frame_count=16_001)
    repository = InMemoryTranscriptionJobRepository()
    job = make_job("over.wav", content)
    repository.save(job)
    destination = BytesIO()

    with pytest.raises(TranscriptionAudioValidationError) as captured:
        ValidateTranscriptionAudio(
            repository,
            FfmpegCanonicalAudioConverter(limits=AudioProcessingLimits(max_duration_seconds=1.0)),
        ).execute(
            job_id=job.job_id,
            source=BytesIO(content),
            destination=destination,
            settings=CanonicalAudioSettings(),
        )

    failed = repository.get(job.job_id)
    assert captured.value.failure_code is JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
    assert failed is not None
    assert failed.status is JobStatus.FAILED
    assert failed.failure_code is JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
    assert destination.getvalue() == b""
    assert TrackingTemporaryDirectory.paths
    assert all(not path.exists() for path in TrackingTemporaryDirectory.paths)


def test_real_mp3_under_duration_limit_is_accepted(tmp_path: Path) -> None:
    source = wav_bytes(sample_rate=16_000, frame_count=4_000)
    content = mp3_bytes_from_wav(source, tmp_path)
    repository, job, destination, result = run_validation(
        filename="short.mp3",
        content=content,
        limits=AudioProcessingLimits(max_duration_seconds=1.0),
    )
    assert repository.get(job.job_id) == job
    assert destination.getvalue().startswith(b"RIFF")
    assert 0 < result.metadata.duration_seconds <= 1.0  # type: ignore[attr-defined]


def test_real_corrupt_content_still_uses_content_invalid_code() -> None:
    content = b"not an audio file"
    repository = InMemoryTranscriptionJobRepository()
    job = make_job("corrupt.wav", content)
    repository.save(job)
    destination = BytesIO()

    with pytest.raises(TranscriptionAudioValidationError) as captured:
        ValidateTranscriptionAudio(
            repository,
            FfmpegCanonicalAudioConverter(limits=AudioProcessingLimits(max_duration_seconds=1.0)),
        ).execute(
            job_id=job.job_id,
            source=BytesIO(content),
            destination=destination,
            settings=CanonicalAudioSettings(),
        )

    failed = repository.get(job.job_id)
    assert captured.value.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert failed is not None
    assert failed.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert destination.getvalue() == b""
