from __future__ import annotations

import subprocess
import wave
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from saxo_ai.application.errors import (
    CanonicalAudioOutputInvalidError,
    CanonicalAudioOutputMissingError,
    FfmpegConversionError,
    FfmpegNotAvailableError,
    FfmpegTimeoutError,
)
from saxo_ai.application.ports import BinaryDestination, BinaryStream
from saxo_ai.domain.audio import (
    CanonicalAudioMetadata,
    CanonicalAudioResult,
    CanonicalAudioSettings,
    OriginalAudioReference,
)

DEFAULT_IO_CHUNK_SIZE = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_STDERR_CHARS = 2_000


@dataclass(frozen=True, slots=True)
class CommandResult:
    return_code: int
    stdout: str
    stderr: str


class CommandExecutor(Protocol):
    def run(self, args: list[str], *, timeout: float, shell: bool) -> CommandResult: ...


class SubprocessCommandExecutor:
    def run(self, args: list[str], *, timeout: float, shell: bool) -> CommandResult:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
        )
        return CommandResult(
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class FfmpegCanonicalAudioConverter:
    def __init__(
        self,
        *,
        executor: CommandExecutor | None = None,
        executable: str = "ffmpeg",
        io_chunk_size: int = DEFAULT_IO_CHUNK_SIZE,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_stderr_chars: int = DEFAULT_MAX_STDERR_CHARS,
    ) -> None:
        if io_chunk_size <= 0:
            raise ValueError("io_chunk_size must be greater than zero")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if max_stderr_chars <= 0:
            raise ValueError("max_stderr_chars must be greater than zero")
        self._executor = executor or SubprocessCommandExecutor()
        self._executable = executable
        self._io_chunk_size = io_chunk_size
        self._timeout_seconds = timeout_seconds
        self._max_stderr_chars = max_stderr_chars

    def convert(
        self,
        *,
        source: BinaryStream,
        destination: BinaryDestination,
        settings: CanonicalAudioSettings,
        original: OriginalAudioReference,
    ) -> CanonicalAudioResult:
        tool_version = self._read_version()

        with TemporaryDirectory(prefix="saxo-canonical-") as workspace:
            workspace_path = Path(workspace)
            source_path = workspace_path / "source.bin"
            output_path = workspace_path / "canonical.wav"
            self._copy_source_to_file(source, source_path)

            command = self._build_conversion_command(source_path, output_path, settings)
            result = self._execute(command)
            if result.return_code != 0:
                raise FfmpegConversionError(
                    return_code=result.return_code,
                    stderr=self._sanitize_stderr(result.stderr, workspace_path),
                )
            if not output_path.is_file():
                raise CanonicalAudioOutputMissingError(
                    "FFmpeg completed without producing a canonical WAV artifact"
                )

            duration_seconds = self._validate_output(output_path, settings)
            self._copy_file_to_destination(output_path, destination)

        return CanonicalAudioResult(
            original=original,
            settings=settings,
            metadata=CanonicalAudioMetadata(
                container=settings.container,
                codec=settings.codec,
                sample_rate_hz=settings.sample_rate_hz,
                channels=settings.channels,
                sample_width_bits=settings.sample_width_bits,
                duration_seconds=duration_seconds,
                tool_name="ffmpeg",
                tool_version=tool_version,
                preprocessing_schema_version=settings.schema_version,
            ),
        )

    def _read_version(self) -> str:
        result = self._execute([self._executable, "-version"])
        if result.return_code != 0:
            raise FfmpegConversionError(
                return_code=result.return_code,
                stderr=self._truncate_and_normalize(result.stderr),
            )
        first_line = next((line for line in result.stdout.splitlines() if line.strip()), "")
        normalized = " ".join(first_line.split())
        if not normalized:
            raise FfmpegConversionError(
                return_code=result.return_code,
                stderr="FFmpeg version output was empty",
            )
        return normalized

    def _execute(self, command: list[str]) -> CommandResult:
        try:
            return self._executor.run(
                command,
                timeout=self._timeout_seconds,
                shell=False,
            )
        except FileNotFoundError as error:
            raise FfmpegNotAvailableError("FFmpeg is not available") from error
        except subprocess.TimeoutExpired as error:
            raise FfmpegTimeoutError(
                f"FFmpeg exceeded the {self._timeout_seconds:g} second timeout"
            ) from error

    def _build_conversion_command(
        self,
        source_path: Path,
        output_path: Path,
        settings: CanonicalAudioSettings,
    ) -> list[str]:
        return [
            self._executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-map",
            "0:a:0",
            "-vn",
            "-map_metadata",
            "-1",
            "-ac",
            str(settings.channels),
            "-ar",
            str(settings.sample_rate_hz),
            "-c:a",
            settings.codec,
            "-f",
            settings.container,
            str(output_path),
        ]

    def _copy_source_to_file(self, source: BinaryStream, path: Path) -> None:
        with path.open("wb") as target:
            for chunk in self._iter_chunks(source):
                target.write(chunk)

    def _copy_file_to_destination(
        self,
        path: Path,
        destination: BinaryDestination,
    ) -> None:
        with path.open("rb") as source:
            for chunk in self._iter_chunks(source):
                self._write_complete_chunk(destination, chunk)

    def _iter_chunks(self, source: BinaryStream) -> Iterator[bytes]:
        while True:
            chunk = source.read(self._io_chunk_size)
            if chunk == b"":
                return
            yield chunk

    @staticmethod
    def _write_complete_chunk(destination: BinaryDestination, chunk: bytes) -> None:
        remaining = memoryview(chunk)
        while remaining:
            written = destination.write(remaining.tobytes())
            if written is None:
                return
            if written <= 0 or written > len(remaining):
                raise OSError("destination returned an invalid write count")
            remaining = remaining[written:]

    @staticmethod
    def _validate_output(path: Path, settings: CanonicalAudioSettings) -> float:
        try:
            with wave.open(str(path), "rb") as output:
                channels = output.getnchannels()
                sample_width = output.getsampwidth()
                sample_rate = output.getframerate()
                frame_count = output.getnframes()
                compression = output.getcomptype()
        except (EOFError, OSError, wave.Error) as error:
            raise CanonicalAudioOutputInvalidError(
                "FFmpeg output is not a readable WAV artifact"
            ) from error

        if compression != "NONE":
            raise CanonicalAudioOutputInvalidError("WAV compression type must be NONE")
        if sample_width != 2:
            raise CanonicalAudioOutputInvalidError("WAV sample width must be 2 bytes")
        if sample_rate != settings.sample_rate_hz:
            raise CanonicalAudioOutputInvalidError("WAV sample rate does not match settings")
        if channels != settings.channels:
            raise CanonicalAudioOutputInvalidError("WAV channels do not match settings")
        if frame_count <= 0:
            raise CanonicalAudioOutputInvalidError("WAV output must contain audio frames")
        return frame_count / sample_rate

    def _sanitize_stderr(self, stderr: str, workspace: Path) -> str:
        sanitized = stderr.replace(str(workspace), "<temporary-workspace>")
        return self._truncate_and_normalize(sanitized)

    def _truncate_and_normalize(self, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) <= self._max_stderr_chars:
            return normalized
        return f"{normalized[: self._max_stderr_chars]}…"
