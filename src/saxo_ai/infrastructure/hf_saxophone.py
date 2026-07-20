from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from importlib import import_module, metadata
from numbers import Real
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Protocol, cast

from saxo_ai.application.ports import BinaryStream
from saxo_ai.application.transcription_errors import (
    InvalidTranscriptionEngineOutputError,
    TranscriptionCheckpointDownloadError,
    TranscriptionCheckpointMismatchError,
    TranscriptionEngineUnavailableError,
    TranscriptionInferenceError,
    TranscriptionModelInitializationError,
)
from saxo_ai.domain.note_events import InvalidNoteEventError, NoteEvent, NoteEventBatch
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)

BASELINE_PACKAGE_NAME = "hf-midi-transcription"
BASELINE_PACKAGE_VERSION = "0.1.1"
MODEL_ID = "xavriley/midi-transcription-models"
MODEL_REVISION = "982ce108d7010bc3c4f36cf851caea8d4c94763d"
CHECKPOINT_FILENAME = "filosax_25k.pth"
CHECKPOINT_SHA256 = "448cf2c8ea6d4b77f7435f5b9a496211ea60300c5c17fa9c754da764f75f3a6a"
CHECKPOINT_SIZE = 99_341_469
SAMPLE_RATE_HZ = 16_000
DEFAULT_DEVICE = "cpu"
DEFAULT_ONSET_THRESHOLD = 0.3
DEFAULT_OFFSET_THRESHOLD = 0.3
DEFAULT_FRAME_THRESHOLD = 0.1
CONFIDENCE_METHOD = "max_reg_onset_activation_pm2_frames"
FRAMES_PER_SECOND = 100
BEGIN_MIDI_NOTE = 21
DEFAULT_COPY_CHUNK_SIZE = 64 * 1024
DEFAULT_CHECKPOINT_CHUNK_SIZE = 1024 * 1024

DEFAULT_SETTINGS = TranscriptionSettings(
    sample_rate_hz=SAMPLE_RATE_HZ,
    device=DEFAULT_DEVICE,
    onset_threshold=DEFAULT_ONSET_THRESHOLD,
    offset_threshold=DEFAULT_OFFSET_THRESHOLD,
    frame_threshold=DEFAULT_FRAME_THRESHOLD,
    confidence_method=CONFIDENCE_METHOD,
)


@dataclass(frozen=True, slots=True)
class BaselineExecutionDiagnostics:
    checkpoint_download_seconds: float
    checkpoint_verification_seconds: float
    initialization_seconds: float
    inference_seconds: float
    event_count: int


class CheckpointDownloader(Protocol):
    def download(self, *, model_id: str, revision: str, filename: str) -> Path: ...


class BaselineRuntime(Protocol):
    def transcribe(self, *, audio_path: Path, midi_path: Path) -> object: ...


class BaselineRuntimeFactory(Protocol):
    def ensure_available(self) -> str: ...

    def create(
        self,
        *,
        checkpoint_path: Path,
        settings: TranscriptionSettings,
    ) -> BaselineRuntime: ...


class HuggingFaceCheckpointDownloader:
    """Resolve only the fixed model, revision, and checkpoint through the HF cache."""

    def download(self, *, model_id: str, revision: str, filename: str) -> Path:
        try:
            hub = import_module("huggingface_hub")
            download = getattr(hub, "hf_hub_download")
            resolved = download(repo_id=model_id, revision=revision, filename=filename)
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
        download_started = self._clock()
        try:
            checkpoint_path = self._downloader.download(
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
        self.last_download_seconds = self._clock() - download_started

        verification_started = self._clock()
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
                while True:
                    chunk = source.read(self._chunk_size)
                    if not chunk:
                        break
                    digest.update(chunk)
            actual_sha256 = digest.hexdigest()
        except TranscriptionCheckpointMismatchError:
            raise
        except OSError as error:
            raise TranscriptionCheckpointDownloadError(
                "Pinned FiloSax checkpoint could not be read for verification"
            ) from error
        finally:
            self.last_verification_seconds = self._clock() - verification_started

        if actual_sha256 != self._expected_sha256:
            raise TranscriptionCheckpointMismatchError(
                expected_sha256=self._expected_sha256,
                actual_sha256=actual_sha256,
                expected_size=self._expected_size,
                actual_size=actual_size,
            )
        self.verified_sha256 = actual_sha256
        return checkpoint_path


class _HfMidiRuntime:
    def __init__(self, model: object) -> None:
        self._model = model

    def transcribe(self, *, audio_path: Path, midi_path: Path) -> object:
        transcribe = getattr(self._model, "transcribe")
        returned = transcribe(audio_path, midi_path, activations=True)
        if not isinstance(returned, tuple) or len(returned) != 2:
            raise InvalidTranscriptionEngineOutputError(
                "baseline runtime must return a MIDI path and activation result"
            )
        return returned[1]


class HfMidiRuntimeFactory:
    def ensure_available(self) -> str:
        try:
            version = metadata.version(BASELINE_PACKAGE_NAME)
        except metadata.PackageNotFoundError as error:
            raise TranscriptionEngineUnavailableError(
                "Optional baseline extra hf-midi-transcription==0.1.1 is not installed"
            ) from error
        if version != BASELINE_PACKAGE_VERSION:
            raise TranscriptionEngineUnavailableError(
                f"Baseline package version {version!r} is incompatible; "
                f"expected {BASELINE_PACKAGE_VERSION!r}"
            )
        return version

    def create(
        self,
        *,
        checkpoint_path: Path,
        settings: TranscriptionSettings,
    ) -> BaselineRuntime:
        try:
            package = import_module("hf_midi_transcription")
            model_class = getattr(package, "MidiTranscriptionModel")
            model = model_class(
                device=settings.device,
                instrument="saxophone",
                checkpoint_path=str(checkpoint_path),
                batch_size=8,
                onset_threshold=settings.onset_threshold,
                offset_threshold=settings.offset_threshold,
                frame_threshold=settings.frame_threshold,
            )
        except Exception as error:
            raise TranscriptionModelInitializationError(
                "Verified FiloSax checkpoint could not initialize the baseline runtime"
            ) from error
        return _HfMidiRuntime(model)


class HfSaxophoneTranscriptionEngine:
    def __init__(
        self,
        *,
        checkpoint_resolver: PinnedFiloSaxCheckpointResolver | None = None,
        runtime_factory: BaselineRuntimeFactory | None = None,
        settings: TranscriptionSettings = DEFAULT_SETTINGS,
        copy_chunk_size: int = DEFAULT_COPY_CHUNK_SIZE,
        temporary_directory_factory: Callable[
            [], AbstractContextManager[str]
        ] | None = None,
        diagnostics_observer: Callable[[BaselineExecutionDiagnostics], None] | None = None,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        if copy_chunk_size <= 0:
            raise ValueError("copy_chunk_size must be positive")
        if settings.sample_rate_hz != SAMPLE_RATE_HZ or settings.device != DEFAULT_DEVICE:
            raise ValueError("FiloSax baseline requires 16000 Hz audio and CPU")
        self._checkpoint_resolver = (
            checkpoint_resolver or PinnedFiloSaxCheckpointResolver()
        )
        self._runtime_factory = runtime_factory or HfMidiRuntimeFactory()
        self._settings = settings
        self._copy_chunk_size = copy_chunk_size
        self._temporary_directory_factory = temporary_directory_factory or (
            lambda: TemporaryDirectory(prefix="saxo-baseline-")
        )
        self._diagnostics_observer = diagnostics_observer
        self._clock = clock

    def transcribe(self, source: BinaryStream) -> TranscriptionResult:
        try:
            engine_version = self._runtime_factory.ensure_available()
        except TranscriptionEngineUnavailableError:
            raise
        except Exception as error:
            raise TranscriptionEngineUnavailableError(
                "Optional pinned saxophone baseline runtime is unavailable"
            ) from error
        if engine_version != BASELINE_PACKAGE_VERSION:
            raise TranscriptionEngineUnavailableError(
                f"Baseline package version {engine_version!r} is incompatible; "
                f"expected {BASELINE_PACKAGE_VERSION!r}"
            )

        with self._temporary_directory_factory() as workspace_value:
            workspace = Path(workspace_value)
            checkpoint_path = self._checkpoint_resolver.resolve()
            audio_path = workspace / "canonical.wav"
            midi_path = workspace / "baseline.mid"
            self._materialize_source(source, audio_path)

            initialization_started = self._clock()
            try:
                runtime = self._runtime_factory.create(
                    checkpoint_path=checkpoint_path,
                    settings=self._settings,
                )
            except TranscriptionModelInitializationError:
                raise
            except Exception as error:
                raise TranscriptionModelInitializationError(
                    "Verified FiloSax checkpoint could not initialize the baseline runtime"
                ) from error
            initialization_seconds = self._clock() - initialization_started

            inference_started = self._clock()
            try:
                external_output = runtime.transcribe(
                    audio_path=audio_path,
                    midi_path=midi_path,
                )
            except InvalidTranscriptionEngineOutputError:
                raise
            except Exception as error:
                raise TranscriptionInferenceError(
                    "Pinned FiloSax baseline inference failed"
                ) from error
            inference_seconds = self._clock() - inference_started
            notes = self._convert_output(external_output)

        result = TranscriptionResult(
            notes=notes,
            model=TranscriptionModelIdentity(
                engine_name=BASELINE_PACKAGE_NAME,
                engine_version=engine_version,
                model_id=MODEL_ID,
                model_revision=MODEL_REVISION,
                checkpoint_filename=CHECKPOINT_FILENAME,
                checkpoint_sha256=self._checkpoint_resolver.verified_sha256,
            ),
            settings=self._settings,
        )
        if self._diagnostics_observer is not None:
            self._diagnostics_observer(
                BaselineExecutionDiagnostics(
                    checkpoint_download_seconds=(
                        self._checkpoint_resolver.last_download_seconds
                    ),
                    checkpoint_verification_seconds=(
                        self._checkpoint_resolver.last_verification_seconds
                    ),
                    initialization_seconds=initialization_seconds,
                    inference_seconds=inference_seconds,
                    event_count=len(notes.events),
                )
            )
        return result

    def _materialize_source(self, source: BinaryStream, destination: Path) -> None:
        try:
            with destination.open("wb") as target:
                while True:
                    chunk = source.read(self._copy_chunk_size)
                    if not chunk:
                        break
                    if not isinstance(chunk, bytes):
                        raise TypeError("source.read(size) must return bytes")
                    target.write(chunk)
        except Exception as error:
            raise TranscriptionInferenceError(
                "Canonical audio could not be materialized for baseline inference"
            ) from error

    def _convert_output(self, external_output: object) -> NoteEventBatch:
        if not isinstance(external_output, dict):
            raise InvalidTranscriptionEngineOutputError(
                "baseline output must be an object"
            )
        raw_events = external_output.get("est_note_events")
        raw_output_dict = external_output.get("output_dict")
        if not isinstance(raw_events, list):
            raise InvalidTranscriptionEngineOutputError("est_note_events must be a list")
        if not isinstance(raw_output_dict, dict):
            raise InvalidTranscriptionEngineOutputError("output_dict must be an object")
        if "reg_onset_output" not in raw_output_dict:
            raise InvalidTranscriptionEngineOutputError(
                "output_dict.reg_onset_output is required"
            )
        onset_matrix = _OnsetMatrix(raw_output_dict["reg_onset_output"])
        notes = tuple(
            self._convert_event(raw_event, onset_matrix, index)
            for index, raw_event in enumerate(raw_events)
        )
        ordered = tuple(
            sorted(
                notes,
                key=lambda event: (
                    event.onset_seconds,
                    event.pitch_concert_midi,
                    event.offset_seconds,
                    event.velocity,
                ),
            )
        )
        return NoteEventBatch(events=ordered)

    @staticmethod
    def _convert_event(
        raw_event: object,
        matrix: _OnsetMatrix,
        index: int,
    ) -> NoteEvent:
        if not isinstance(raw_event, dict):
            raise InvalidTranscriptionEngineOutputError(
                "event must be an object",
                event_index=index,
            )
        required = ("onset_time", "offset_time", "midi_note", "velocity")
        missing = [field for field in required if field not in raw_event]
        if missing:
            raise InvalidTranscriptionEngineOutputError(
                f"missing required field(s): {', '.join(missing)}",
                event_index=index,
            )
        try:
            onset = raw_event["onset_time"]
            pitch = raw_event["midi_note"]
            confidence = matrix.confidence(onset=onset, pitch=pitch)
            return NoteEvent(
                pitch_concert_midi=pitch,
                onset_seconds=onset,
                offset_seconds=raw_event["offset_time"],
                velocity=raw_event["velocity"],
                confidence=confidence,
            )
        except (InvalidNoteEventError, ValueError, TypeError) as error:
            raise InvalidTranscriptionEngineOutputError(
                str(error),
                event_index=index,
            ) from error


class _OnsetMatrix:
    def __init__(self, matrix: object) -> None:
        self._matrix = matrix
        shape = getattr(matrix, "shape", None)
        if shape is not None:
            if not isinstance(shape, Sequence) or len(shape) != 2:
                raise InvalidTranscriptionEngineOutputError(
                    "reg_onset_output must be a two-dimensional matrix"
                )
            self._frames = int(shape[0])
            self._pitches = int(shape[1])
            self._numpy_style = True
        elif isinstance(matrix, (list, tuple)):
            if not matrix or not all(
                isinstance(row, (list, tuple)) for row in matrix
            ):
                raise InvalidTranscriptionEngineOutputError(
                    "reg_onset_output must be a non-empty two-dimensional matrix"
                )
            rows = cast(Sequence[Sequence[object]], matrix)
            self._frames = len(rows)
            self._pitches = len(rows[0])
            if self._pitches == 0 or any(
                len(row) != self._pitches for row in rows
            ):
                raise InvalidTranscriptionEngineOutputError(
                    "reg_onset_output rows must have a consistent positive width"
                )
            self._numpy_style = False
        else:
            raise InvalidTranscriptionEngineOutputError(
                "reg_onset_output must be a two-dimensional matrix"
            )
        if self._frames <= 0 or self._pitches <= 0:
            raise InvalidTranscriptionEngineOutputError(
                "reg_onset_output must contain frames and pitch classes"
            )

    def confidence(self, *, onset: object, pitch: object) -> float:
        if isinstance(onset, bool) or not isinstance(onset, Real):
            raise ValueError("onset_time must be a finite number")
        onset_value = float(onset)
        if not math.isfinite(onset_value) or onset_value < 0:
            raise ValueError("onset_time must be a finite non-negative number")
        if isinstance(pitch, bool) or not isinstance(pitch, int):
            raise ValueError("midi_note must be a Python integer")
        pitch_index = pitch - BEGIN_MIDI_NOTE
        if not 0 <= pitch_index < self._pitches:
            raise ValueError("midi_note has no corresponding onset activation")
        center_frame = round(onset_value * FRAMES_PER_SECOND)
        window_start = max(0, center_frame - 2)
        window_end = min(self._frames, center_frame + 3)
        if window_start >= window_end:
            raise ValueError("onset activation window contains no frames")
        values = [
            self._value(frame, pitch_index)
            for frame in range(window_start, window_end)
        ]
        return max(values)

    def _value(self, frame: int, pitch: int) -> float:
        try:
            if self._numpy_style:
                raw = self._matrix[frame, pitch]  # type: ignore[index]
            else:
                raw = self._matrix[frame][pitch]  # type: ignore[index]
        except Exception as error:
            raise ValueError("onset activation could not be indexed") from error
        if isinstance(raw, bool) or not isinstance(raw, Real):
            raise ValueError("onset activation must be numeric")
        value = float(raw)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(
                "onset activation must be finite and between 0.0 and 1.0"
            )
        return value
