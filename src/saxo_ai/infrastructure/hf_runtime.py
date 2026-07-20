from __future__ import annotations

import warnings
from importlib import import_module, metadata
from pathlib import Path
from typing import Protocol, cast

from saxo_ai.application.transcription_errors import (
    InvalidTranscriptionEngineOutputError,
    TranscriptionEngineUnavailableError,
    TranscriptionModelInitializationError,
)
from saxo_ai.domain.transcription import TranscriptionSettings
from saxo_ai.infrastructure.hf_baseline_contract import (
    BASELINE_PACKAGE_NAME,
    BASELINE_PACKAGE_VERSION,
    BaselineRuntime,
)

_AUDIOREAD_STDLIB_DEPRECATION = (
    r"'(?:aifc|sunau)' is deprecated and slated for removal in Python 3\.13"
)


class _ExternalTranscriptionModel(Protocol):
    def transcribe(
        self,
        audio_path: Path,
        midi_path: Path,
        *,
        activations: bool,
    ) -> object: ...


class _HfMidiRuntime:
    def __init__(self, model: object) -> None:
        self._model = cast(_ExternalTranscriptionModel, model)

    def transcribe(self, *, audio_path: Path, midi_path: Path) -> object:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=_AUDIOREAD_STDLIB_DEPRECATION,
                category=DeprecationWarning,
            )
            returned = self._model.transcribe(audio_path, midi_path, activations=True)
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
            model = package.MidiTranscriptionModel(
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
