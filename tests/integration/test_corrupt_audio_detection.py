from __future__ import annotations

import hashlib
import math
import os
import shutil
import struct
import wave
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory as RealTemporaryDirectory
from uuid import uuid4

import pytest

from saxo_ai.application.audio_validation import ValidateTranscriptionAudio
from saxo_ai.application.errors import TranscriptionAudioValidationError
from saxo_ai.domain.audio import CanonicalAudioSettings
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
        pytest.skip("ffmpeg is not installed; corrupt-audio integration tests skipped")
    yield


class TrackingTemporaryDirectory:
    paths: list[Path] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._delegate = RealTemporaryDirectory(*args, **kwargs)

    def __enter__(self) -> str:
        path = self._delegate.__enter__()
        self.paths.append(Path(path))
        return path

    def __exit__(self, *args: object) -> None:
        self._delegate.__exit__(*args)


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


def synthetic_wav_bytes() -> bytes:
    destination = BytesIO()
    sample_rate = 44100
    with wave.open(destination, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = bytearray()
        for index in range(sample_rate):
            sample = round(10000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        output.writeframes(frames)
    return destination.getvalue()


def test_real_corrupt_wav_marks_existing_job_failed_without_destination_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from saxo_ai.infrastructure import ffmpeg as ffmpeg_module

    TrackingTemporaryDirectory.paths.clear()
    monkeypatch.setattr(ffmpeg_module, "TemporaryDirectory", TrackingTemporaryDirectory)
    content = b"these bytes are not a wav file"
    job = make_job("corrupt.wav", content)
    repository = InMemoryTranscriptionJobRepository()
    repository.save(job)
    destination = BytesIO()

    with pytest.raises(TranscriptionAudioValidationError) as captured:
        ValidateTranscriptionAudio(repository, FfmpegCanonicalAudioConverter()).execute(
            job_id=job.job_id,
            source=BytesIO(content),
            destination=destination,
            settings=CanonicalAudioSettings(),
        )

    failed = repository.get(job.job_id)
    assert captured.value.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert failed is not None
    assert failed.status is JobStatus.FAILED
    assert failed.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert destination.getvalue() == b""
    assert TrackingTemporaryDirectory.paths
    assert all(not path.exists() for path in TrackingTemporaryDirectory.paths)


def test_real_valid_wav_returns_canonical_result_and_keeps_job_uploaded() -> None:
    content = synthetic_wav_bytes()
    job = make_job("valid.wav", content)
    repository = InMemoryTranscriptionJobRepository()
    repository.save(job)
    destination = BytesIO()

    result = ValidateTranscriptionAudio(repository, FfmpegCanonicalAudioConverter()).execute(
        job_id=job.job_id,
        source=BytesIO(content),
        destination=destination,
        settings=CanonicalAudioSettings(),
    )

    stored = repository.get(job.job_id)
    assert stored == job
    assert stored is not None
    assert stored.status is JobStatus.UPLOADED
    assert stored.failure_code is None
    assert result.original.filename == "valid.wav"
    assert destination.getvalue().startswith(b"RIFF")
    with wave.open(BytesIO(destination.getvalue()), "rb") as canonical:
        assert canonical.getframerate() == 16000
        assert canonical.getnchannels() == 1
        assert canonical.getsampwidth() == 2
