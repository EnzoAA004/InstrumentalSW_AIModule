from __future__ import annotations

import math
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import Any

import pytest

from saxo_ai.domain.note_events import (
    NOTE_EVENT_SCHEMA_VERSION,
    InvalidNoteEventError,
    NoteEvent,
    NoteEventBatch,
    UnsupportedNoteEventSchemaVersionError,
)


def make_event(**overrides: Any) -> NoteEvent:
    values: dict[str, Any] = {
        "pitch_concert_midi": 60,
        "onset_seconds": 0.0,
        "offset_seconds": 0.5,
        "velocity": 100,
        "confidence": 0.92,
    }
    values.update(overrides)
    return NoteEvent(**values)


def test_valid_note_event_exposes_exact_immutable_normalized_contract() -> None:
    event = make_event(onset_seconds=0, offset_seconds=1, confidence=1)

    assert event.pitch_concert_midi == 60
    assert event.onset_seconds == 0.0
    assert type(event.onset_seconds) is float
    assert event.offset_seconds == 1.0
    assert type(event.offset_seconds) is float
    assert event.velocity == 100
    assert event.confidence == 1.0
    assert type(event.confidence) is float
    assert event.duration_seconds == 1.0
    assert [field.name for field in fields(event)] == [
        "pitch_concert_midi",
        "onset_seconds",
        "offset_seconds",
        "velocity",
        "confidence",
    ]

    with pytest.raises(FrozenInstanceError):
        event.velocity = 1  # type: ignore[misc]
    assert not hasattr(event, "__dict__")


@pytest.mark.parametrize("pitch", [0, 127])
def test_pitch_concert_midi_accepts_midi_boundaries(pitch: int) -> None:
    assert make_event(pitch_concert_midi=pitch).pitch_concert_midi == pitch


@pytest.mark.parametrize("pitch", [-1, 128, 60.0, True, "60"])
def test_pitch_concert_midi_rejects_out_of_range_and_non_integer_values(pitch: Any) -> None:
    with pytest.raises(InvalidNoteEventError, match="pitch_concert_midi"):
        make_event(pitch_concert_midi=pitch)


@pytest.mark.parametrize("onset", [0, 0.0])
def test_onset_seconds_accepts_zero_and_normalizes_to_float(onset: int | float) -> None:
    assert make_event(onset_seconds=onset).onset_seconds == 0.0
    assert type(make_event(onset_seconds=onset).onset_seconds) is float


@pytest.mark.parametrize("onset", [-0.001, math.nan, math.inf, -math.inf, True, "0", None])
def test_onset_seconds_rejects_invalid_values(onset: Any) -> None:
    with pytest.raises(InvalidNoteEventError, match="onset_seconds"):
        make_event(onset_seconds=onset)


@pytest.mark.parametrize(
    ("onset", "offset"),
    [
        (0.5, 0.5),
        (0.5, 0.4),
        (0.0, math.nan),
        (0.0, math.inf),
        (0.0, -math.inf),
        (0.0, True),
        (0.0, "0.5"),
        (0.0, None),
    ],
)
def test_offset_seconds_must_be_finite_numeric_and_greater_than_onset(
    onset: float,
    offset: Any,
) -> None:
    with pytest.raises(InvalidNoteEventError, match="offset_seconds"):
        make_event(onset_seconds=onset, offset_seconds=offset)


@pytest.mark.parametrize("velocity", [0, 127])
def test_velocity_accepts_midi_boundaries(velocity: int) -> None:
    assert make_event(velocity=velocity).velocity == velocity


@pytest.mark.parametrize("velocity", [-1, 128, 64.0, True, "64"])
def test_velocity_rejects_out_of_range_and_non_integer_values(velocity: Any) -> None:
    with pytest.raises(InvalidNoteEventError, match="velocity"):
        make_event(velocity=velocity)


@pytest.mark.parametrize("confidence", [0, 0.0, 1, 1.0])
def test_confidence_accepts_boundaries_and_normalizes_to_float(
    confidence: int | float,
) -> None:
    event = make_event(confidence=confidence)
    assert event.confidence == float(confidence)
    assert type(event.confidence) is float


@pytest.mark.parametrize("confidence", [-0.001, 1.001, math.nan, math.inf, -math.inf, True, "0.9"])
def test_confidence_rejects_invalid_values(confidence: Any) -> None:
    with pytest.raises(InvalidNoteEventError, match="confidence"):
        make_event(confidence=confidence)


def test_note_event_batch_accepts_empty_and_normalizes_sequence_to_tuple() -> None:
    empty = NoteEventBatch(events=())
    event = make_event()
    batch = NoteEventBatch(events=[event])  # type: ignore[arg-type]

    assert empty.events == ()
    assert empty.schema_version == NOTE_EVENT_SCHEMA_VERSION == "1.0"
    assert batch.events == (event,)
    assert isinstance(batch.events, tuple)
    with pytest.raises(FrozenInstanceError):
        batch.schema_version = "2.0"  # type: ignore[misc]
    assert not hasattr(batch, "__dict__")


@pytest.mark.parametrize("schema_version", ["", "2.0", 1, None])
def test_note_event_batch_rejects_unsupported_schema_versions(schema_version: Any) -> None:
    with pytest.raises(UnsupportedNoteEventSchemaVersionError):
        NoteEventBatch(events=(), schema_version=schema_version)


@pytest.mark.parametrize("events", [None, "events", [object()], [1]])
def test_note_event_batch_rejects_non_note_event_members(events: Any) -> None:
    with pytest.raises(InvalidNoteEventError, match="events"):
        NoteEventBatch(events=events)


def test_note_event_domain_has_no_forbidden_dependencies() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/saxo_ai/domain/note_events.py").read_text(encoding="utf-8").lower()
    for forbidden in ("fastapi", "ffmpeg", "subprocess", "tempfile", "pydantic"):
        assert forbidden not in source
