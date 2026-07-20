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
    EmptyAudioFileError,
    TranscriptionAudioValidationError,
    UnsupportedAudioFormatError,
)
from saxo_ai.application.services import CreateTranscriptionJob
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
        self._content = content
        self._offset = 0
        self.requested_sizes: list[int] = []
        self.returned_bytes = 0

    def read(self, size: int) -> bytes:
        assert size > 0
        self.requested_sizes.append(size)
        chunk = self._content[self._offset : self._offset + size]
        self._offset += len(chunk)
        self.returned_bytes += len(chunk)
        return chunk

    @property
    def remaining_bytes(self) -> int:
        return len(self._content) - self._offset


class ExplodingStream:
    def read(self, size: int) -> bytes:
        raise AssertionError(f"stream must not be read; requested {size}")


class RecordingRepository(InMemoryTranscriptionJobRepository):
    def __init__(self) -> None:
        super().__init__()
        self.saved: list[TranscriptionJob] = []

    def save(self, job: TranscriptionJob) -> None:
        self.saved.append(job)
        super().save(job)


class DurationRejectingConverter:
    def convert(self, **_: Any) -> Any:
        raise AudioDurationLimitExceededError(
            max_duration_seconds=1.0,
            actual_duration_seconds=1.0000625,
        )


def test_audio_processing_limits_defaults_and_custom_values() -> None:
    defaults = AudioProcessingLimits()
    assert defaults.max_size_bytes == 104_857_600
    assert defaults.max_duration_seconds == 900.0

    custom = AudioProcessingLimits(max_size_bytes=8, max_duration_seconds=1.5)
    assert custom.max_size_bytes == 8
    assert custom.max_duration_seconds == 1.5


@pytest.mark.parametrize("invalid", [0, -1, True, False, 1.5, "8"])
def test_audio_processing_limits_reject_invalid_size(invalid: object) -> None:
    with pytest.raises((TypeError, ValueError), match="max_size_bytes"):
        AudioProcessingLimits(max_size_bytes=invalid)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid",
    [0, -1, True, False, math.nan, math.inf, -math.inf, "900"],
)
def test_audio_processing_limits_reject_invalid_duration(invalid: object) -> None:
    with pytest.raises((TypeError, ValueError), match="max_duration_seconds"):
        AudioProcessingLimits(max_duration_seconds=invalid)  # type: ignore[arg-type]


def test_environment_loader_uses_defaults_and_valid_overrides() -> None:
    assert load_audio_processing_limits({}) == AudioProcessingLimits()
    assert load_audio_processing_limits(
        {
            "SAXO_MAX_AUDIO_SIZE_BYTES": "8",
            "SAXO_MAX_AUDIO_DURATION_SECONDS": "1.25",
        }
    ) == AudioProcessingLimits(max_size_bytes=8, max_duration_seconds=1.25)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SAXO_MAX_AUDIO_SIZE_BYTES", "0"),
        ("SAXO_MAX_AUDIO_SIZE_BYTES", "-1"),
        ("SAXO_MAX_AUDIO_SIZE_BYTES", "1.5"),
        ("SAXO_MAX_AUDIO_SIZE_BYTES", "true"),
        ("SAXO_MAX_AUDIO_DURATION_SECONDS", "0"),
        ("SAXO_MAX_AUDIO_DURATION_SECONDS", "-1"),
        ("SAXO_MAX_AUDIO_DURATION_SECONDS", "nan"),
        ("SAXO_MAX_AUDIO_DURATION_SECONDS", "inf"),
        ("SAXO_MAX_AUDIO_DURATION_SECONDS", "true"),
    ],
)
def test_environment_loader_rejects_invalid_values(name: str, value: str) -> None:
    with pytest.raises(AudioProcessingConfigurationError, match=name):
        load_audio_processing_limits({name: value})


def test_create_app_fails_for_invalid_runtime_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAXO_MAX_AUDIO_SIZE_BYTES", "invalid")
    with pytest.raises(AudioProcessingConfigurationError, match="SAXO_MAX_AUDIO_SIZE_BYTES"):
        create_app()


def test_hasher_accepts_exact_size_limit_and_returns_complete_hash() -> None:
    content = b"12345678"
    stream = SpyStream(content)
    metadata = Sha256AudioContentHasher(max_size_bytes=8, chunk_size=64).inspect(stream)
    assert metadata.size_bytes == 8
    assert metadata.audio_sha256 == hashlib.sha256(content).hexdigest()
    assert stream.returned_bytes == 8
    assert stream.remaining_bytes == 0
    assert stream.requested_sizes == [9, 1]


def test_hasher_stops_at_one_byte_over_limit_without_returning_metadata() -> None:
    stream = SpyStream(b"0123456789-extra-content")
    with pytest.raises(AudioSizeLimitExceededError) as captured:
        Sha256AudioContentHasher(max_size_bytes=8, chunk_size=64).inspect(stream)
    assert captured.value.max_size_bytes == 8
    assert captured.value.observed_size_bytes == 9
    assert stream.returned_bytes == 9
    assert stream.remaining_bytes > 0
    assert stream.requested_sizes == [9]


def test_unsupported_extension_precedes_stream_read_and_repository_save() -> None:
    repository = RecordingRepository()
    service = CreateTranscriptionJob(
        repository,
        Sha256AudioContentHasher(max_size_bytes=1),
    )
    with pytest.raises(UnsupportedAudioFormatError):
        service.execute(
            filename="audio.flac",
            content=ExplodingStream(),
            saxophone_type=SaxophoneType.ALTO,
            input_mode=InputMode.SOLO,
        )
    assert repository.saved == []


def test_empty_file_remains_empty_error_without_saved_job() -> None:
    repository = RecordingRepository()
    service = CreateTranscriptionJob(
        repository,
        Sha256AudioContentHasher(max_size_bytes=8),
    )
    with pytest.raises(EmptyAudioFileError):
        service.execute(
            filename="empty.wav",
            content=BytesIO(),
            saxophone_type=SaxophoneType.ALTO,
            input_mode=InputMode.SOLO,
        )
    assert repository.saved == []


def test_size_limit_error_prevents_job_save() -> None:
    repository = RecordingRepository()
    service = CreateTranscriptionJob(
        repository,
        Sha256AudioContentHasher(max_size_bytes=8),
    )
    with pytest.raises(AudioSizeLimitExceededError):
        service.execute(
            filename="large.wav",
            content=BytesIO(b"123456789"),
            saxophone_type=SaxophoneType.ALTO,
            input_mode=InputMode.SOLO,
        )
    assert repository.saved == []


def test_http_accepts_exact_size_limit_and_persists_hash() -> None:
    content = b"12345678"
    with TestClient(
        create_app(limits=AudioProcessingLimits(max_size_bytes=8, max_duration_seconds=1.0))
    ) as client:
        response = post_audio(client, filename="exact.wav", content=content)
        assert response.status_code == 202
        payload = response.json()
        assert payload["size_bytes"] == 8
        assert payload["audio_sha256"] == hashlib.sha256(content).hexdigest()
        assert "failure_code" not in payload
        fetched = client.get(f"/api/v1/transcriptions/{payload['job_id']}")
        assert fetched.status_code == 200
        assert fetched.json() == payload
        assert client.get("/health").status_code == 200


def test_http_rejects_one_byte_over_limit_with_structured_413() -> None:
    with TestClient(
        create_app(limits=AudioProcessingLimits(max_size_bytes=8, max_duration_seconds=1.0))
    ) as client:
        response = post_audio(client, filename="large.wav", content=b"123456789")
    assert response.status_code == 413
    assert response.json() == {
        "detail": {
            "code": "AUDIO_SIZE_LIMIT_EXCEEDED",
            "message": "Audio exceeds the maximum allowed size of 8 bytes.",
            "max_size_bytes": 8,
        }
    }
    assert "job_id" not in response.json()["detail"]
    assert "observed_size_bytes" not in response.json()["detail"]


def test_duration_limit_marks_job_failed_with_distinct_code() -> None:
    repository = RecordingRepository()
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
    repository.saved.clear()

    with pytest.raises(TranscriptionAudioValidationError) as captured:
        ValidateTranscriptionAudio(repository, DurationRejectingConverter()).execute(
            job_id=job.job_id,
            source=BytesIO(b"valid audio"),
            destination=BytesIO(),
            settings=CanonicalAudioSettings(),
        )

    assert captured.value.failure_code is JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED
    assert repository.saved == [job.mark_failed(JobFailureCode.AUDIO_DURATION_LIMIT_EXCEEDED)]


def post_audio(client: TestClient, *, filename: str, content: bytes) -> Any:
    return client.post(
        "/api/v1/transcriptions",
        files={"file": (filename, content, "application/octet-stream")},
        data={"saxophone_type": "alto", "input_mode": "solo"},
    )
