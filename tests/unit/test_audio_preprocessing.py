from __future__ import annotations

import ast
import subprocess
import wave
from dataclasses import replace
from pathlib import Path

import pytest

from saxo_ai.application.audio_preprocessing import ConvertToCanonicalAudio
from saxo_ai.application.errors import (
    CanonicalAudioOutputInvalidError,
    CanonicalAudioOutputMissingError,
    FfmpegConversionError,
    FfmpegNotAvailableError,
    FfmpegTimeoutError,
)
from saxo_ai.domain.audio import (
    CanonicalAudioSettings,
    InvalidCanonicalAudioSettingsError,
    OriginalAudioReference,
)
from saxo_ai.infrastructure.ffmpeg import (
    CommandResult,
    FfmpegCanonicalAudioConverter,
)

ROOT = Path(__file__).resolve().parents[2]
KNOWN_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class NonSeekableSource:
    def __init__(self, content: bytes, *, maximum_read_size: int) -> None:
        self._content = content
        self._position = 0
        self._maximum_read_size = maximum_read_size
        self.requested_sizes: list[int] = []

    def read(self, size: int) -> bytes:
        if not isinstance(size, int):
            raise AssertionError("read() requires an explicit integer size")
        if not 0 < size <= self._maximum_read_size:
            raise AssertionError(f"unbounded source read: {size}")
        self.requested_sizes.append(size)
        chunk = self._content[self._position : self._position + size]
        self._position += len(chunk)
        return chunk

    def write(self, _data: bytes) -> int:
        raise AssertionError("the original source must never be modified")


class RecordingDestination:
    def __init__(self, *, maximum_write_size: int) -> None:
        self.maximum_write_size = maximum_write_size
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> int:
        if not 0 < len(data) <= self.maximum_write_size:
            raise AssertionError(f"unbounded destination write: {len(data)}")
        self.writes.append(bytes(data))
        return len(data)


class RecordingExecutor:
    def __init__(
        self,
        *,
        conversion_return_code: int = 0,
        conversion_stderr: str = "",
        create_output: bool = True,
        valid_output: bool = True,
        raise_missing: bool = False,
        raise_timeout: bool = False,
    ) -> None:
        self.conversion_return_code = conversion_return_code
        self.conversion_stderr = conversion_stderr
        self.create_output = create_output
        self.valid_output = valid_output
        self.raise_missing = raise_missing
        self.raise_timeout = raise_timeout
        self.calls: list[tuple[list[str], float, bool]] = []
        self.observed_paths: list[Path] = []

    def run(self, args: list[str], *, timeout: float, shell: bool) -> CommandResult:
        self.calls.append((list(args), timeout, shell))
        if self.raise_missing:
            raise FileNotFoundError("ffmpeg")
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(args, timeout)
        if args[-1] == "-version":
            return CommandResult(0, "ffmpeg version test-7.1\n", "")

        input_path = Path(args[args.index("-i") + 1])
        output_path = Path(args[-1])
        self.observed_paths.extend([input_path, output_path])
        assert input_path.is_file()

        if self.create_output:
            if self.valid_output:
                channels = int(args[args.index("-ac") + 1])
                sample_rate = int(args[args.index("-ar") + 1])
                write_wave(output_path, channels=channels, sample_rate=sample_rate, frames=32)
            else:
                output_path.write_bytes(b"not-a-wave")

        return CommandResult(
            self.conversion_return_code,
            "",
            self.conversion_stderr,
        )


def write_wave(path: Path, *, channels: int, sample_rate: int, frames: int) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * channels * frames)


def original_reference() -> OriginalAudioReference:
    return OriginalAudioReference(
        filename="user take.wav",
        size_bytes=3,
        audio_sha256=KNOWN_SHA256,
    )


def test_default_canonical_settings_are_explicit_and_reproducible() -> None:
    settings = CanonicalAudioSettings()

    assert settings.sample_rate_hz == 16000
    assert settings.channels == 1
    assert settings.container == "wav"
    assert settings.codec == "pcm_s16le"
    assert settings.sample_width_bits == 16
    assert settings.amplitude_normalization == "none"
    assert settings.schema_version == "1.0"


@pytest.mark.parametrize(
    "changes",
    [
        {"sample_rate_hz": 0},
        {"sample_rate_hz": -1},
        {"channels": 0},
        {"channels": 3},
        {"container": "mp3"},
        {"codec": "aac"},
        {"sample_width_bits": 24},
        {"amplitude_normalization": "peak"},
    ],
)
def test_invalid_canonical_settings_fail_before_ffmpeg(changes: dict[str, object]) -> None:
    with pytest.raises(InvalidCanonicalAudioSettingsError):
        CanonicalAudioSettings(**changes)  # type: ignore[arg-type]


def test_conversion_preserves_original_reference_and_records_exact_metadata() -> None:
    executor = RecordingExecutor()
    converter = FfmpegCanonicalAudioConverter(
        executor=executor,
        io_chunk_size=8,
        timeout_seconds=17,
    )
    source = NonSeekableSource(b"source-bytes-across-blocks", maximum_read_size=8)
    destination = RecordingDestination(maximum_write_size=8)
    original = original_reference()
    settings = CanonicalAudioSettings(sample_rate_hz=22050, channels=2)

    result = ConvertToCanonicalAudio(converter).execute(
        source=source,
        destination=destination,
        settings=settings,
        original=original,
    )

    assert result.original is original
    assert result.original == original
    assert result.settings == settings
    assert result.metadata.container == "wav"
    assert result.metadata.codec == "pcm_s16le"
    assert result.metadata.sample_rate_hz == 22050
    assert result.metadata.channels == 2
    assert result.metadata.sample_width_bits == 16
    assert result.metadata.tool_name == "ffmpeg"
    assert result.metadata.tool_version == "ffmpeg version test-7.1"
    assert result.metadata.preprocessing_schema_version == settings.schema_version
    assert result.metadata.duration_seconds == pytest.approx(32 / 22050)

    assert source.requested_sizes
    assert set(source.requested_sizes) == {8}
    assert len(destination.writes) > 1
    assert b"".join(destination.writes).startswith(b"RIFF")

    version_call, conversion_call = executor.calls
    assert version_call == (["ffmpeg", "-version"], 17, False)
    args, timeout, shell = conversion_call
    assert isinstance(args, list)
    assert timeout == 17
    assert shell is False
    assert args[args.index("-ac") + 1] == "2"
    assert args[args.index("-ar") + 1] == "22050"
    assert args[args.index("-c:a") + 1] == "pcm_s16le"
    assert args[args.index("-f") + 1] == "wav"
    assert "user take.wav" not in " ".join(args)
    assert not hasattr(result, "path")

    for path in executor.observed_paths:
        assert not path.exists()
        assert not path.parent.exists()


def test_ffmpeg_missing_is_reported_with_stable_error() -> None:
    converter = FfmpegCanonicalAudioConverter(executor=RecordingExecutor(raise_missing=True))

    with pytest.raises(FfmpegNotAvailableError):
        ConvertToCanonicalAudio(converter).execute(
            source=NonSeekableSource(b"input", maximum_read_size=65536),
            destination=RecordingDestination(maximum_write_size=65536),
            settings=CanonicalAudioSettings(),
            original=original_reference(),
        )


def test_ffmpeg_timeout_is_reported_with_stable_error() -> None:
    converter = FfmpegCanonicalAudioConverter(
        executor=RecordingExecutor(raise_timeout=True), timeout_seconds=3
    )

    with pytest.raises(FfmpegTimeoutError, match="3"):
        ConvertToCanonicalAudio(converter).execute(
            source=NonSeekableSource(b"input", maximum_read_size=65536),
            destination=RecordingDestination(maximum_write_size=65536),
            settings=CanonicalAudioSettings(),
            original=original_reference(),
        )


def test_ffmpeg_nonzero_exit_sanitizes_and_truncates_stderr_and_cleans_workspace() -> None:
    executor = RecordingExecutor(
        conversion_return_code=7,
        conversion_stderr="temporary failure " * 500,
        create_output=False,
    )
    converter = FfmpegCanonicalAudioConverter(executor=executor, max_stderr_chars=120)

    with pytest.raises(FfmpegConversionError) as captured:
        ConvertToCanonicalAudio(converter).execute(
            source=NonSeekableSource(b"input", maximum_read_size=65536),
            destination=RecordingDestination(maximum_write_size=65536),
            settings=CanonicalAudioSettings(),
            original=original_reference(),
        )

    assert captured.value.return_code == 7
    assert len(captured.value.stderr) <= 121
    assert captured.value.stderr.endswith("…")
    for path in executor.observed_paths:
        assert str(path) not in captured.value.stderr
        assert not path.parent.exists()


def test_missing_output_is_not_reported_as_success() -> None:
    converter = FfmpegCanonicalAudioConverter(
        executor=RecordingExecutor(create_output=False),
    )

    with pytest.raises(CanonicalAudioOutputMissingError):
        ConvertToCanonicalAudio(converter).execute(
            source=NonSeekableSource(b"input", maximum_read_size=65536),
            destination=RecordingDestination(maximum_write_size=65536),
            settings=CanonicalAudioSettings(),
            original=original_reference(),
        )


def test_invalid_wav_output_is_not_reported_as_success() -> None:
    converter = FfmpegCanonicalAudioConverter(
        executor=RecordingExecutor(valid_output=False),
    )

    with pytest.raises(CanonicalAudioOutputInvalidError):
        ConvertToCanonicalAudio(converter).execute(
            source=NonSeekableSource(b"input", maximum_read_size=65536),
            destination=RecordingDestination(maximum_write_size=65536),
            settings=CanonicalAudioSettings(),
            original=original_reference(),
        )


def test_fixed_canonical_fields_cannot_be_changed_after_creation() -> None:
    settings = CanonicalAudioSettings()

    with pytest.raises(InvalidCanonicalAudioSettingsError):
        replace(settings, codec="flac")


def test_architecture_keeps_preprocessing_out_of_fastapi_and_domain() -> None:
    route_source = (ROOT / "src" / "saxo_ai" / "api" / "routes.py").read_text(encoding="utf-8")
    main_source = (ROOT / "src" / "saxo_ai" / "main.py").read_text(encoding="utf-8")
    assert "CanonicalAudio" not in route_source
    assert "CanonicalAudio" not in main_source
    assert "ffmpeg" not in route_source.lower()

    for folder in ("application", "domain"):
        for path in sorted((ROOT / "src" / "saxo_ai" / folder).glob("*.py")):
            source = path.read_text(encoding="utf-8")
            assert "fastapi" not in source
            if folder == "domain":
                assert "subprocess" not in source
                assert "tempfile" not in source
                assert "pathlib" not in source

    ffmpeg_source = (ROOT / "src" / "saxo_ai" / "infrastructure" / "ffmpeg.py").read_text(
        encoding="utf-8"
    )
    assert "import subprocess" in ffmpeg_source
    assert "TemporaryDirectory" in ffmpeg_source
    assert ast.parse(ffmpeg_source)
