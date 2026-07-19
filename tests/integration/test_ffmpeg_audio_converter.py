from __future__ import annotations

import hashlib
import math
import os
import shutil
import struct
import subprocess
import wave
from collections.abc import Iterator
from pathlib import Path

import pytest

from saxo_ai.application.audio_preprocessing import ConvertToCanonicalAudio
from saxo_ai.domain.audio import CanonicalAudioSettings, OriginalAudioReference
from saxo_ai.infrastructure.ffmpeg import FfmpegCanonicalAudioConverter

pytestmark = pytest.mark.integration
DURATION_TOLERANCE_SECONDS = 0.10


class NonSeekableFileSource:
    def __init__(self, path: Path) -> None:
        self._file = path.open("rb")
        self.requested_sizes: list[int] = []

    def read(self, size: int) -> bytes:
        if size <= 0:
            raise AssertionError("source read must be bounded")
        self.requested_sizes.append(size)
        return self._file.read(size)

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> NonSeekableFileSource:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


@pytest.fixture(scope="module", autouse=True)
def require_ffmpeg() -> Iterator[None]:
    if shutil.which("ffmpeg") is None:
        if os.environ.get("SAXO_REQUIRE_FFMPEG") == "1":
            pytest.fail("SAXO_REQUIRE_FFMPEG=1 but ffmpeg is not installed")
        pytest.skip("ffmpeg is not installed; real integration tests skipped")
    yield


def write_synthetic_wave(
    path: Path,
    *,
    sample_rate: int = 44100,
    channels: int = 2,
    duration_seconds: float = 1.0,
    frequency_hz: float | None = 440.0,
) -> None:
    frame_count = round(sample_rate * duration_seconds)
    frames = bytearray()
    for frame_index in range(frame_count):
        sample = (
            0
            if frequency_hz is None
            else round(12000 * math.sin(2 * math.pi * frequency_hz * frame_index / sample_rate))
        )
        frames.extend(struct.pack("<h", sample) * channels)

    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(frames)


def reference_for(path: Path) -> OriginalAudioReference:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return OriginalAudioReference(
        filename=path.name,
        size_bytes=size,
        audio_sha256=digest.hexdigest(),
    )


def inspect_wave(path: Path) -> tuple[int, int, int, float]:
    with wave.open(str(path), "rb") as audio:
        assert audio.getcomptype() == "NONE"
        channels = audio.getnchannels()
        sample_rate = audio.getframerate()
        sample_width = audio.getsampwidth()
        duration = audio.getnframes() / sample_rate
    return channels, sample_rate, sample_width, duration


def convert_file(
    source_path: Path,
    destination_path: Path,
    settings: CanonicalAudioSettings,
) -> tuple[object, list[int]]:
    converter = FfmpegCanonicalAudioConverter()
    with NonSeekableFileSource(source_path) as source, destination_path.open("wb") as destination:
        result = ConvertToCanonicalAudio(converter).execute(
            source=source,
            destination=destination,
            settings=settings,
            original=reference_for(source_path),
        )
        requested_sizes = source.requested_sizes
    return result, requested_sizes


def assert_external_ffmpeg_validation(path: Path) -> None:
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def test_real_wav_converts_to_default_canonical_format(tmp_path: Path) -> None:
    source = tmp_path / "sine-a4.wav"
    canonical = tmp_path / "canonical.wav"
    write_synthetic_wave(source, sample_rate=44100, channels=2, frequency_hz=440.0)

    result, requested_sizes = convert_file(source, canonical, CanonicalAudioSettings())

    channels, sample_rate, sample_width, duration = inspect_wave(canonical)
    assert (channels, sample_rate, sample_width) == (1, 16000, 2)
    assert abs(duration - 1.0) <= DURATION_TOLERANCE_SECONDS
    assert result.metadata.duration_seconds == pytest.approx(duration)
    assert result.metadata.tool_name == "ffmpeg"
    assert result.metadata.tool_version.startswith("ffmpeg version ")
    assert requested_sizes and set(requested_sizes) == {64 * 1024}
    assert_external_ffmpeg_validation(canonical)


def test_real_wav_supports_22050_hz_stereo_configuration(tmp_path: Path) -> None:
    source = tmp_path / "silence.wav"
    canonical = tmp_path / "canonical-stereo.wav"
    write_synthetic_wave(source, sample_rate=32000, channels=1, frequency_hz=None)
    settings = CanonicalAudioSettings(sample_rate_hz=22050, channels=2)

    result, _ = convert_file(source, canonical, settings)

    channels, sample_rate, sample_width, duration = inspect_wave(canonical)
    assert (channels, sample_rate, sample_width) == (2, 22050, 2)
    assert abs(duration - 1.0) <= DURATION_TOLERANCE_SECONDS
    assert result.settings == settings
    assert_external_ffmpeg_validation(canonical)


def test_real_mp3_converts_to_default_canonical_format(tmp_path: Path) -> None:
    wav_source = tmp_path / "source.wav"
    mp3_source = tmp_path / "source.mp3"
    canonical = tmp_path / "canonical-from-mp3.wav"
    write_synthetic_wave(wav_source, sample_rate=44100, channels=2, frequency_hz=440.0)
    encoded = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(wav_source),
            str(mp3_source),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert encoded.returncode == 0, encoded.stderr

    result, _ = convert_file(mp3_source, canonical, CanonicalAudioSettings())

    channels, sample_rate, sample_width, duration = inspect_wave(canonical)
    assert (channels, sample_rate, sample_width) == (1, 16000, 2)
    assert abs(duration - 1.0) <= DURATION_TOLERANCE_SECONDS
    assert result.original == reference_for(mp3_source)
    assert_external_ffmpeg_validation(canonical)
