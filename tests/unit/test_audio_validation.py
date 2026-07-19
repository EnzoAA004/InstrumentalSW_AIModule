from __future__ import annotations

from dataclasses import FrozenInstanceError
from io import BytesIO
from typing import Protocol
from uuid import UUID, uuid4

import pytest

from saxo_ai.application.audio_validation import ValidateTranscriptionAudio
from saxo_ai.application.errors import (
    AudioContentInvalidError,
    CanonicalAudioOutputInvalidError,
    CanonicalAudioOutputMissingError,
    FfmpegNotAvailableError,
    FfmpegTimeoutError,
    TranscriptionAudioValidationError,
    TranscriptionJobNotFoundError,
)
from saxo_ai.application.ports import BinaryDestination, BinaryStream
from saxo_ai.domain.audio import (
    CanonicalAudioMetadata,
    CanonicalAudioResult,
    CanonicalAudioSettings,
    OriginalAudioReference,
)
from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
    TranscriptionJob,
)
from saxo_ai.infrastructure.ffmpeg import CommandResult, FfmpegCanonicalAudioConverter

KNOWN_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class ConverterLike(Protocol):
    def convert(
        self,
        *,
        source: BinaryStream,
        destination: BinaryDestination,
        settings: CanonicalAudioSettings,
        original: OriginalAudioReference,
    ) -> CanonicalAudioResult: ...


class RecordingRepository:
    def __init__(self, job: TranscriptionJob | None) -> None:
        self._job = job
        self.saved: list[TranscriptionJob] = []

    def get(self, job_id: UUID) -> TranscriptionJob | None:
        if self._job is not None and self._job.job_id == job_id:
            return self._job
        return None

    def save(self, job: TranscriptionJob) -> None:
        self._job = job
        self.saved.append(job)


class FakeConverter:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.originals: list[OriginalAudioReference] = []

    def convert(
        self,
        *,
        source: BinaryStream,
        destination: BinaryDestination,
        settings: CanonicalAudioSettings,
        original: OriginalAudioReference,
    ) -> CanonicalAudioResult:
        self.originals.append(original)
        if self.error is not None:
            raise self.error
        assert source.read(1) in {b"", b"a"}
        destination.write(b"canonical-wav")
        return CanonicalAudioResult(
            original=original,
            settings=settings,
            metadata=CanonicalAudioMetadata(
                container="wav",
                codec="pcm_s16le",
                sample_rate_hz=settings.sample_rate_hz,
                channels=settings.channels,
                sample_width_bits=16,
                duration_seconds=1.0,
                tool_name="ffmpeg",
                tool_version="ffmpeg version test",
                preprocessing_schema_version=settings.schema_version,
            ),
        )


class DifferentiatingExecutor:
    def __init__(self, *, version_code: int = 0, conversion_code: int = 0) -> None:
        self.version_code = version_code
        self.conversion_code = conversion_code

    def run(self, args: list[str], *, timeout: float, shell: bool) -> CommandResult:
        assert timeout > 0
        assert shell is False
        if args[-1] == "-version":
            return CommandResult(self.version_code, "ffmpeg version fake\n", "same stderr")
        return CommandResult(self.conversion_code, "", "same stderr")


def build_job() -> TranscriptionJob:
    return TranscriptionJob(
        job_id=uuid4(),
        status=JobStatus.UPLOADED,
        filename="take.wav",
        size_bytes=3,
        audio_sha256=KNOWN_SHA256,
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )


def test_new_job_is_uploaded_without_failure_code_and_is_immutable() -> None:
    job = build_job()
    assert job.status is JobStatus.UPLOADED
    assert job.failure_code is None
    with pytest.raises(FrozenInstanceError):
        job.status = JobStatus.FAILED  # type: ignore[misc]


def test_mark_failed_returns_new_job_and_preserves_original_fields() -> None:
    original = build_job()
    failed = original.mark_failed(JobFailureCode.AUDIO_CONTENT_INVALID)
    assert failed is not original
    assert original.status is JobStatus.UPLOADED
    assert original.failure_code is None
    assert failed.status is JobStatus.FAILED
    assert failed.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert failed.job_id == original.job_id
    assert failed.filename == original.filename
    assert failed.size_bytes == original.size_bytes
    assert failed.audio_sha256 == original.audio_sha256
    assert failed.saxophone_type == original.saxophone_type
    assert failed.input_mode == original.input_mode


def test_failed_job_requires_code_and_non_failed_job_rejects_code() -> None:
    base = build_job()
    with pytest.raises(ValueError, match="FAILED"):
        TranscriptionJob(
            job_id=base.job_id,
            status=JobStatus.FAILED,
            filename=base.filename,
            size_bytes=base.size_bytes,
            audio_sha256=base.audio_sha256,
            saxophone_type=base.saxophone_type,
            input_mode=base.input_mode,
        )
    with pytest.raises(ValueError, match="non-failed"):
        TranscriptionJob(
            job_id=base.job_id,
            status=JobStatus.UPLOADED,
            filename=base.filename,
            size_bytes=base.size_bytes,
            audio_sha256=base.audio_sha256,
            saxophone_type=base.saxophone_type,
            input_mode=base.input_mode,
            failure_code=JobFailureCode.AUDIO_CONTENT_INVALID,
        )


def test_success_returns_result_without_resaving_or_changing_job() -> None:
    job = build_job()
    repository = RecordingRepository(job)
    converter = FakeConverter()
    destination = BytesIO()
    result = ValidateTranscriptionAudio(repository, converter).execute(
        job_id=job.job_id,
        source=BytesIO(b"a"),
        destination=destination,
        settings=CanonicalAudioSettings(),
    )
    assert result.original == OriginalAudioReference(
        filename=job.filename,
        size_bytes=job.size_bytes,
        audio_sha256=job.audio_sha256,
    )
    assert converter.originals == [result.original]
    assert destination.getvalue() == b"canonical-wav"
    assert repository.saved == []
    assert repository.get(job.job_id) == job
    assert job.status is JobStatus.UPLOADED
    assert job.failure_code is None


def test_invalid_content_marks_job_failed_and_raises_stable_application_error() -> None:
    job = build_job()
    repository = RecordingRepository(job)
    converter = FakeConverter(error=AudioContentInvalidError(return_code=1, stderr="decoder"))
    destination = BytesIO()
    with pytest.raises(TranscriptionAudioValidationError) as captured:
        ValidateTranscriptionAudio(repository, converter).execute(
            job_id=job.job_id,
            source=BytesIO(b"broken"),
            destination=destination,
            settings=CanonicalAudioSettings(),
        )
    assert captured.value.job_id == job.job_id
    assert captured.value.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert destination.getvalue() == b""
    assert len(repository.saved) == 1
    failed = repository.saved[0]
    assert failed.status is JobStatus.FAILED
    assert failed.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert failed.filename == job.filename
    assert failed.audio_sha256 == job.audio_sha256
    assert not hasattr(failed, "stderr")
    assert not hasattr(failed, "path")


@pytest.mark.parametrize(
    "technical_error",
    [
        FfmpegNotAvailableError("missing"),
        FfmpegTimeoutError("timeout"),
        CanonicalAudioOutputMissingError("missing output"),
        CanonicalAudioOutputInvalidError("bad output"),
    ],
)
def test_technical_errors_propagate_without_marking_job_failed(technical_error: Exception) -> None:
    job = build_job()
    repository = RecordingRepository(job)
    destination = BytesIO()
    with pytest.raises(type(technical_error)):
        ValidateTranscriptionAudio(repository, FakeConverter(error=technical_error)).execute(
            job_id=job.job_id,
            source=BytesIO(b"audio"),
            destination=destination,
            settings=CanonicalAudioSettings(),
        )
    assert repository.saved == []
    assert repository.get(job.job_id) == job
    assert job.status is JobStatus.UPLOADED
    assert job.failure_code is None
    assert destination.getvalue() == b""


def test_unknown_job_uses_existing_not_found_error_without_conversion() -> None:
    repository = RecordingRepository(None)
    converter = FakeConverter()
    with pytest.raises(TranscriptionJobNotFoundError):
        ValidateTranscriptionAudio(repository, converter).execute(
            job_id=uuid4(),
            source=BytesIO(b"audio"),
            destination=BytesIO(),
            settings=CanonicalAudioSettings(),
        )
    assert converter.originals == []


def test_version_failure_is_technical_but_conversion_nonzero_is_content_invalid() -> None:
    common = dict(
        source=BytesIO(b"invalid"),
        destination=BytesIO(),
        settings=CanonicalAudioSettings(),
        original=OriginalAudioReference(
            filename="take.wav", size_bytes=7, audio_sha256=KNOWN_SHA256
        ),
    )
    with pytest.raises(Exception) as version_error:
        FfmpegCanonicalAudioConverter(
            executor=DifferentiatingExecutor(version_code=2),
        ).convert(**common)
    assert not isinstance(version_error.value, AudioContentInvalidError)
    with pytest.raises(AudioContentInvalidError):
        FfmpegCanonicalAudioConverter(
            executor=DifferentiatingExecutor(conversion_code=2),
        ).convert(**common)
