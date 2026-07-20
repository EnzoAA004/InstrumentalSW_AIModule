from __future__ import annotations

from dataclasses import FrozenInstanceError
from io import BytesIO
from typing import Any

import pytest

from saxo_ai.application.transcription import TranscribeCanonicalAudio, TranscriptionEngine
from saxo_ai.application.transcription_errors import TranscriptionInferenceError
from saxo_ai.domain.note_events import NoteEventBatch
from saxo_ai.domain.transcription import (
    InvalidTranscriptionContractError,
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)

MODEL_SHA = "448cf2c8ea6d4b77f7435f5b9a496211ea60300c5c17fa9c754da764f75f3a6a"


def model_identity(**overrides: Any) -> TranscriptionModelIdentity:
    values: dict[str, Any] = {
        "engine_name": "hf-midi-transcription",
        "engine_version": "0.1.1",
        "model_id": "xavriley/midi-transcription-models",
        "model_revision": "982ce108d7010bc3c4f36cf851caea8d4c94763d",
        "checkpoint_filename": "filosax_25k.pth",
        "checkpoint_sha256": MODEL_SHA,
    }
    values.update(overrides)
    return TranscriptionModelIdentity(**values)


def settings(**overrides: Any) -> TranscriptionSettings:
    values: dict[str, Any] = {
        "sample_rate_hz": 16000,
        "device": "cpu",
        "onset_threshold": 0.3,
        "offset_threshold": 0.3,
        "frame_threshold": 0.1,
        "confidence_method": "max_reg_onset_activation_pm2_frames",
    }
    values.update(overrides)
    return TranscriptionSettings(**values)


def result() -> TranscriptionResult:
    return TranscriptionResult(notes=NoteEventBatch(events=()), model=model_identity(), settings=settings())


def test_model_identity_records_exact_pinned_provenance_and_is_immutable() -> None:
    identity = model_identity()
    assert identity.engine_name == "hf-midi-transcription"
    assert identity.engine_version == "0.1.1"
    assert identity.model_id == "xavriley/midi-transcription-models"
    assert identity.model_revision == "982ce108d7010bc3c4f36cf851caea8d4c94763d"
    assert identity.checkpoint_filename == "filosax_25k.pth"
    assert identity.checkpoint_sha256 == MODEL_SHA
    with pytest.raises(FrozenInstanceError):
        identity.engine_version = "future"  # type: ignore[misc]
    assert not hasattr(identity, "__dict__")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("engine_name", ""),
        ("engine_version", ""),
        ("model_id", ""),
        ("model_revision", ""),
        ("checkpoint_filename", ""),
        ("checkpoint_sha256", "A" * 64),
        ("checkpoint_sha256", "0" * 63),
        ("checkpoint_sha256", "g" * 64),
        ("engine_name", 1),
    ],
)
def test_model_identity_rejects_invalid_fields(field: str, value: object) -> None:
    with pytest.raises(InvalidTranscriptionContractError, match=field):
        model_identity(**{field: value})


def test_settings_and_result_are_immutable_and_allow_empty_note_batch() -> None:
    transcription_settings = settings()
    transcription_result = result()
    assert transcription_settings.sample_rate_hz == 16000
    assert transcription_settings.device == "cpu"
    assert transcription_settings.onset_threshold == 0.3
    assert transcription_settings.offset_threshold == 0.3
    assert transcription_settings.frame_threshold == 0.1
    assert transcription_settings.confidence_method == "max_reg_onset_activation_pm2_frames"
    assert transcription_result.notes.events == ()
    assert transcription_result.model == model_identity()
    assert transcription_result.settings == transcription_settings
    with pytest.raises(FrozenInstanceError):
        transcription_result.notes = NoteEventBatch(events=())  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sample_rate_hz", 0),
        ("sample_rate_hz", True),
        ("sample_rate_hz", 16000.0),
        ("device", ""),
        ("device", 1),
        ("onset_threshold", -0.1),
        ("offset_threshold", 1.1),
        ("frame_threshold", float("nan")),
        ("frame_threshold", True),
        ("confidence_method", ""),
    ],
)
def test_settings_reject_invalid_values(field: str, value: object) -> None:
    with pytest.raises(InvalidTranscriptionContractError, match=field):
        settings(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("notes", object()),
        ("model", object()),
        ("settings", object()),
    ],
)
def test_result_rejects_wrong_contract_types(field: str, value: object) -> None:
    values: dict[str, object] = {
        "notes": NoteEventBatch(events=()),
        "model": model_identity(),
        "settings": settings(),
    }
    values[field] = value
    with pytest.raises(InvalidTranscriptionContractError, match=field):
        TranscriptionResult(**values)


class FakeEngine:
    def __init__(self, expected: TranscriptionResult) -> None:
        self.expected = expected
        self.sources: list[object] = []

    def transcribe(self, source: object) -> TranscriptionResult:
        self.sources.append(source)
        return self.expected


def test_use_case_delegates_once_with_same_stream_and_returns_same_result() -> None:
    expected = result()
    engine = FakeEngine(expected)
    source = BytesIO(b"canonical wav")
    use_case = TranscribeCanonicalAudio(engine)
    assert isinstance(engine, TranscriptionEngine)
    actual = use_case.execute(source)
    assert actual is expected
    assert engine.sources == [source]


class FailingEngine:
    def transcribe(self, source: object) -> TranscriptionResult:
        raise TranscriptionInferenceError("controlled inference failure")


def test_use_case_propagates_controlled_engine_errors_without_translation() -> None:
    use_case = TranscribeCanonicalAudio(FailingEngine())
    with pytest.raises(TranscriptionInferenceError, match="controlled"):
        use_case.execute(BytesIO(b"wav"))
