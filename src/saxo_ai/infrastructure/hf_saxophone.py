from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from saxo_ai.application.ports import BinaryStream
from saxo_ai.application.transcription_errors import (
    InvalidTranscriptionEngineOutputError,
    TranscriptionEngineUnavailableError,
    TranscriptionInferenceError,
    TranscriptionModelInitializationError,
)
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.infrastructure.hf_baseline_contract import (
    BASELINE_PACKAGE_NAME,
    BASELINE_PACKAGE_VERSION,
    BEGIN_MIDI_NOTE,
    CHECKPOINT_FILENAME,
    CHECKPOINT_SHA256,
    CHECKPOINT_SIZE,
    CONFIDENCE_METHOD,
    DEFAULT_COPY_CHUNK_SIZE,
    DEFAULT_DEVICE,
    DEFAULT_SETTINGS,
    FRAMES_PER_SECOND,
    MODEL_ID,
    MODEL_REVISION,
    SAMPLE_RATE_HZ,
    BaselineExecutionDiagnostics,
    BaselineRuntime,
    BaselineRuntimeFactory,
    DiagnosticsObserver,
)
from saxo_ai.infrastructure.hf_checkpoint import PinnedFiloSaxCheckpointResolver
from saxo_ai.infrastructure.hf_output import convert_baseline_output
from saxo_ai.infrastructure.hf_runtime import HfMidiRuntimeFactory

__all__ = [
    "BASELINE_PACKAGE_NAME",
    "BASELINE_PACKAGE_VERSION",
    "BEGIN_MIDI_NOTE",
    "CHECKPOINT_FILENAME",
    "CHECKPOINT_SHA256",
    "CHECKPOINT_SIZE",
    "CONFIDENCE_METHOD",
    "FRAMES_PER_SECOND",
    "MODEL_ID",
    "MODEL_REVISION",
    "BaselineExecutionDiagnostics",
    "HfSaxophoneTranscriptionEngine",
    "PinnedFiloSaxCheckpointResolver",
]


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
        diagnostics_observer: DiagnosticsObserver | None = None,
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
        engine_version = self._ensure_runtime()
        with self._temporary_directory_factory() as workspace_value:
            workspace = Path(workspace_value)
            checkpoint_path = self._checkpoint_resolver.resolve()
            audio_path = workspace / "canonical.wav"
            midi_path = workspace / "baseline.mid"
            self._materialize_source(source, audio_path)
            runtime, initialization_seconds = self._initialize(checkpoint_path)
            external_output, inference_seconds = self._infer(
                runtime,
                audio_path,
                midi_path,
            )
            notes = convert_baseline_output(external_output)

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
        self._report(initialization_seconds, inference_seconds, len(notes.events))
        return result

    def _ensure_runtime(self) -> str:
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
        return engine_version

    def _materialize_source(self, source: BinaryStream, destination: Path) -> None:
        try:
            with destination.open("wb") as target:
                while chunk := source.read(self._copy_chunk_size):
                    if not isinstance(chunk, bytes):
                        raise TypeError("source.read(size) must return bytes")
                    target.write(chunk)
        except Exception as error:
            raise TranscriptionInferenceError(
                "Canonical audio could not be materialized for baseline inference"
            ) from error

    def _initialize(self, checkpoint_path: Path) -> tuple[BaselineRuntime, float]:
        started = self._clock()
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
        return runtime, self._clock() - started

    def _infer(
        self,
        runtime: BaselineRuntime,
        audio_path: Path,
        midi_path: Path,
    ) -> tuple[object, float]:
        started = self._clock()
        try:
            output = runtime.transcribe(audio_path=audio_path, midi_path=midi_path)
        except InvalidTranscriptionEngineOutputError:
            raise
        except Exception as error:
            raise TranscriptionInferenceError(
                "Pinned FiloSax baseline inference failed"
            ) from error
        return output, self._clock() - started

    def _report(
        self,
        initialization_seconds: float,
        inference_seconds: float,
        event_count: int,
    ) -> None:
        if self._diagnostics_observer is None:
            return
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
                event_count=event_count,
            )
        )
