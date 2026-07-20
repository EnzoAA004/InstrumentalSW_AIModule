from __future__ import annotations

import math
import re
from dataclasses import dataclass

from saxo_ai.domain.note_events import NoteEventBatch

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class InvalidTranscriptionContractError(ValueError):
    """Raised when transcription provenance or settings violate the domain contract."""


def _non_empty_string(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidTranscriptionContractError(f"{field_name} must be a non-empty string")
    return value


def _unit_interval(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTranscriptionContractError(
            f"{field_name} must be a finite number from 0.0 to 1.0"
        )
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise InvalidTranscriptionContractError(
            f"{field_name} must be a finite number from 0.0 to 1.0"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class TranscriptionModelIdentity:
    engine_name: str
    engine_version: str
    model_id: str
    model_revision: str
    checkpoint_filename: str
    checkpoint_sha256: str

    def __post_init__(self) -> None:
        for field_name in (
            "engine_name",
            "engine_version",
            "model_id",
            "model_revision",
            "checkpoint_filename",
        ):
            object.__setattr__(
                self, field_name, _non_empty_string(field_name, getattr(self, field_name))
            )
        if (
            not isinstance(self.checkpoint_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.checkpoint_sha256) is None
        ):
            raise InvalidTranscriptionContractError(
                "checkpoint_sha256 must be 64 lowercase hexadecimal characters"
            )


@dataclass(frozen=True, slots=True)
class TranscriptionSettings:
    sample_rate_hz: int
    device: str
    onset_threshold: float
    offset_threshold: float
    frame_threshold: float
    confidence_method: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.sample_rate_hz, bool)
            or not isinstance(self.sample_rate_hz, int)
            or self.sample_rate_hz <= 0
        ):
            raise InvalidTranscriptionContractError("sample_rate_hz must be a positive integer")
        object.__setattr__(self, "device", _non_empty_string("device", self.device))
        object.__setattr__(
            self,
            "onset_threshold",
            _unit_interval("onset_threshold", self.onset_threshold),
        )
        object.__setattr__(
            self,
            "offset_threshold",
            _unit_interval("offset_threshold", self.offset_threshold),
        )
        object.__setattr__(
            self,
            "frame_threshold",
            _unit_interval("frame_threshold", self.frame_threshold),
        )
        object.__setattr__(
            self,
            "confidence_method",
            _non_empty_string("confidence_method", self.confidence_method),
        )


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    notes: NoteEventBatch
    model: TranscriptionModelIdentity
    settings: TranscriptionSettings

    def __post_init__(self) -> None:
        if not isinstance(self.notes, NoteEventBatch):
            raise InvalidTranscriptionContractError("notes must be a NoteEventBatch")
        if not isinstance(self.model, TranscriptionModelIdentity):
            raise InvalidTranscriptionContractError("model must be a TranscriptionModelIdentity")
        if not isinstance(self.settings, TranscriptionSettings):
            raise InvalidTranscriptionContractError("settings must be TranscriptionSettings")
