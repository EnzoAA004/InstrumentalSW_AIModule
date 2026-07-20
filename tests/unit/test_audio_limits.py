from __future__ import annotations

import hashlib
import math
from io import BytesIO
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from saxo_ai.application.audio_validation import ValidateTranscriptionAudio
from saxo_ai.application.errors import (
    AudioDurationLimitExceededError,
    AudioSizeLimitExceededError,
    TranscriptionAudioValidationError,
)
from saxo_ai.domain.audio import AudioProcessingLimits, CanonicalAudioSettings
from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
    TranscriptionJob,
)
from saxo_ai.infrastructure.configuration import (
    AudioProcessingConfigurationError,
    load_audio_processing_limits,
)
from saxo_ai.infrastructure.hashing import Sha256AudioContentHasher
from saxo_ai.infrastructure.repositories import InMemoryTranscriptionJobRepository
from saxo_ai.main import create_app


class SpyStream:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.offset = 0
        self.requests: list[int] = []

    def read(self, size: int) -> bytes:
        assert size > 0
        self.requests.append(size)
        chunk = self.content[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class DurationRejectingConverter:
    def convert(self, **_: Any) -> Any:
        raise AudioDurationLimitExceededError(
            max_duration_seconds=1.0,
            actual_duration_seconds=1.0000625,
        )


def post_audio(client: TestClient, content: bytes) -> Any:
    return client.post(
        "/api/v1/transcriptions",
        files={"file": ("take.wav", content, "application/octet-stream")},
        data={"saxophone_type": "alto", "input_mode": "solo"},
    )


def test_limits_defaults_custom_and_invalid_values() -> None:
    assert AudioProcessingLimits() == AudioProcessingLimits(
        max_size_bytes=104_857_600,
        max_duration_seconds=900.0,
    )
    assert AudioProcessingLimits(max_size_bytes=8, max_duration_seconds=1.5).max_size_bytes == 8
    for value in (0, -1, True, 1.5):
        with pytest.raises((TypeError, ValueError), match="max_size_bytes"):
            AudioProcessingLimits(max_size_bytes=value)  # type: ignore[arg-type]
    for value in (0, -1, True, math.nan, math.inf):
        with pytest.raises((TypeError, ValueError), match="max_duration_seconds"):
            AudioProcessingLimits(max_duration_seconds=value)  # type: ignore[arg-type]


def test_environment_configuration_defaults_valid_and_invalid() -> None:
    assert load_audio_processing_limits({}) == AudioProcessingLimits()
    assert load_audio_processing_limits(
        {
            "SAXO_MAX_AUDIO_SIZE_BYTES": "8",
            "SAXO_MAX_AUDIO_DURATION_SECONDS": "1.25",
        }
    ) == AudioProcessingLimits(max_size_bytes=8, max_duration_seconds=1.25)
    for name, value in (
        ("SAXO_MAX_AUDIO_SIZE_BYTES", "invalid"),
        ("SAXO_MAX_AUDIO_SIZE_BYTES", "0"),
        ("SAXO_MAX_AUDIO_DURATION_SECONDS", "nan"),
        ("SAXO_MAX_AUDIO_DURATION_SECONDS", "0"),
    ):
        with pytest.raises(AudioProcessingConfigurationError, match=name):
            load_audio_processing_limits({name: value})


def test_incremental_hasher_accepts_n_and_stops_at_n_plus_one() -> None:
    exact = SpyStream(b"12345678")
    metadata = Sha256AudioContentHasher(max_size_bytes=8, chunk_size=64).inspect(exact)
    assert metadata.size_bytes == 8
    assert metadata.audio_sha256 == hashlib.sha256(b"12345678").hexdigest()
    assert exact.requests == [9, 1]

    oversized = SpyStream(b"123456789-extra")
    with pytest.raises(AudioSizeLimitExceededError) as captured:
        Sha256AudioContentHasher(max_size_bytes=8, chunk_size=64).inspect(oversized)
    assert captured.value.max_size_bytes == 8
    assert captured.value.observed_size_bytes == 9
    assert oversized.offset == 9
    assert oversized.requests == [9]


def test_http_exact_limit_and_structured_413() -> None:
    limits = AudioProcessingLimits(max_size_bytes=8, max_duration_seconds=1.0)
    with TestClient(create_app(limits=limits)) as client:
        accepted = post_audio(client, b"12345678")
        assert accepted.status_code == 202
        assert accepted.json()["size_bytes"] == 8
        rejected = post_audio(client, b"123456789")
        assert rejected.status_code == 413
        assert rejected.json() == {
            "detail": {
                "code": "AUDIO_SIZE_LIMIT_EXCEEDED",
                "message": "Audio exceeds the maximum allowed size of 8 bytes.",
                "max_size_bytes": 8,
            }
        }


def test_duration_limit_uses_distinct_failed_job_code() -> None:
    repository = InMemoryTranscriptionJobRepository()
    job = TranscriptionJob(
        job_id=UUID("00000000-0000-0000-0000-000000000013"),
        status=JobStatus.UPLOADED,
        filename="long.wav",
        size_bytes=10,
        audio_sha256="0" * 64,
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )
    repository.save(job)
    with pytest.raises(TranscriptionAudioValidationError) as captured:
        ValidateTranscriptionAudio(repository, DurationRejectingConverter()).execute(
            job_id=job.job_id,
            source=BytesIO(b"audio"),
            destination=BytesIO(),
            settings=CanonicalAudioSettings(),
        )
    assert captured.value.failure_code is JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
    assert repository.get(job.job_id) == job.mark_failed(
        JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
    )
