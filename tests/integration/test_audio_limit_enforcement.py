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


def wav_bytes(frame_count: int, sample_rate: int = 16_000) -> bytes:
    destination = BytesIO()
    with wave.open(destination, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(
            b"".join(
                struct.pack(
                    "<h",
                    round(8000 * math.sin(2 * math.pi * 440 * index / sample_rate)),
                )
                for index in range(frame_count)
            )
        )
    return destination.getvalue()


def mp3_bytes(content: bytes, tmp_path: Path) -> bytes:
    source = tmp_path / "source.wav"
    output = tmp_path / "source.mp3"
    source.write_bytes(content)
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), str(output)],
        check=True,
        capture_output=True,
    )
    return output.read_bytes()


def validate(filename: str, content: bytes, maximum: float) -> tuple[object, bytes, TranscriptionJob]:
    repository = InMemoryTranscriptionJobRepository()
    job = TranscriptionJob(
        job_id=uuid4(),
        status=JobStatus.UPLOADED,
        filename=filename,
        size_bytes=len(content),
        audio_sha256=hashlib.sha256(content).hexdigest(),
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )
    repository.save(job)
    destination = BytesIO()
    result = ValidateTranscriptionAudio(
        repository,
        FfmpegCanonicalAudioConverter(
            limits=AudioProcessingLimits(max_duration_seconds=maximum)
        ),
    ).execute(
        job_id=job.job_id,
        source=BytesIO(content),
        destination=destination,
        settings=CanonicalAudioSettings(),
    )
    assert repository.get(job.job_id) == job
    return result, destination.getvalue(), job


def test_real_wav_exact_duration_limit_is_accepted() -> None:
    result, output, job = validate("exact.wav", wav_bytes(16_000), 1.0)
    assert result.metadata.duration_seconds == 1.0  # type: ignore[attr-defined]
    assert output.startswith(b"RIFF")
    assert job.failure_code is None


def test_real_wav_one_frame_over_limit_fails_with_empty_destination() -> None:
    content = wav_bytes(16_001)
    repository = InMemoryTranscriptionJobRepository()
    job = TranscriptionJob(
        job_id=uuid4(), status=JobStatus.UPLOADED, filename="over.wav",
        size_bytes=len(content), audio_sha256=hashlib.sha256(content).hexdigest(),
        saxophone_type=SaxophoneType.ALTO, input_mode=InputMode.SOLO,
    )
    repository.save(job)
    destination = BytesIO()
    with pytest.raises(TranscriptionAudioValidationError) as captured:
        ValidateTranscriptionAudio(
            repository,
            FfmpegCanonicalAudioConverter(
                limits=AudioProcessingLimits(max_duration_seconds=1.0)
            ),
        ).execute(
            job_id=job.job_id, source=BytesIO(content), destination=destination,
            settings=CanonicalAudioSettings(),
        )
    assert captured.value.failure_code is JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
    assert repository.get(job.job_id).failure_code is JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED  # type: ignore[union-attr]
    assert destination.getvalue() == b""


def test_real_mp3_under_limit_and_corrupt_content_code(tmp_path: Path) -> None:
    result, output, _ = validate("short.mp3", mp3_bytes(wav_bytes(4_000), tmp_path), 1.0)
    assert 0 < result.metadata.duration_seconds <= 1.0  # type: ignore[attr-defined]
    assert output.startswith(b"RIFF")

    corrupt = b"not an audio file"
    repository = InMemoryTranscriptionJobRepository()
    job = TranscriptionJob(
        job_id=uuid4(), status=JobStatus.UPLOADED, filename="corrupt.wav",
        size_bytes=len(corrupt), audio_sha256=hashlib.sha256(corrupt).hexdigest(),
        saxophone_type=SaxophoneType.ALTO, input_mode=InputMode.SOLO,
    )
    repository.save(job)
    with pytest.raises(TranscriptionAudioValidationError) as captured:
        ValidateTranscriptionAudio(
            repository,
            FfmpegCanonicalAudioConverter(
                limits=AudioProcessingLimits(max_duration_seconds=1.0)
            ),
        ).execute(
            job_id=job.job_id, source=BytesIO(corrupt), destination=BytesIO(),
            settings=CanonicalAudioSettings(),
        )
    assert captured.value.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
