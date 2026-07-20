from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from saxo_ai.domain.transcription import TranscriptionSettings

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


DiagnosticsObserver = Callable[[BaselineExecutionDiagnostics], None]
