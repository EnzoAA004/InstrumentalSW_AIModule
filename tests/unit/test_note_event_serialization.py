from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from saxo_ai.application.note_event_serialization import (
    InvalidNoteEventPayloadError,
    deserialize_note_event_batch,
    serialize_note_event_batch,
)
from saxo_ai.domain.note_events import (
    NOTE_EVENT_FIELDS,
    InvalidNoteEventError,
    NoteEvent,
    NoteEventBatch,
    UnsupportedNoteEventSchemaVersionError,
)


def event(
    *,
    pitch: int = 60,
    onset: float = 0.0,
    offset: float = 0.5,
    velocity: int = 100,
    confidence: float = 0.92,
) -> NoteEvent:
    return NoteEvent(
        pitch_concert_midi=pitch,
        onset_seconds=onset,
        offset_seconds=offset,
        velocity=velocity,
        confidence=confidence,
    )


def valid_document() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "events": [
            {
                "pitch_concert_midi": 60,
                "onset_seconds": 0.0,
                "offset_seconds": 0.5,
                "velocity": 100,
                "confidence": 0.92,
            }
        ],
    }


def test_empty_batch_is_serializable_with_required_root_fields() -> None:
    payload = serialize_note_event_batch(NoteEventBatch(events=()))
    assert json.loads(payload) == {"schema_version": "1.0", "events": []}


def test_serializer_uses_exact_public_fields_and_excludes_deferred_fields() -> None:
    batch = NoteEventBatch(events=(event(),))
    first_payload = serialize_note_event_batch(batch)
    second_payload = serialize_note_event_batch(batch)
    document = json.loads(first_payload)

    assert first_payload == second_payload
    assert set(document) == {"schema_version", "events"}
    assert tuple(document["events"][0]) == tuple(sorted(NOTE_EVENT_FIELDS))
    assert set(document["events"][0]) == set(NOTE_EVENT_FIELDS)
    for forbidden in (
        "source_model",
        "checkpoint",
        "model_version",
        "written_pitch",
        "note_name",
        "frequency_hz",
        "low_confidence",
        "quantized_onset",
        "quantized_offset",
        "duration_seconds",
    ):
        assert forbidden not in first_payload
    assert batch == NoteEventBatch(events=(event(),))


def test_round_trip_preserves_value_order_duplicates_and_overlaps() -> None:
    late = event(pitch=67, onset=1.0, offset=1.5)
    duplicate = event(pitch=60, onset=0.0, offset=0.75)
    overlap = event(pitch=64, onset=0.5, offset=1.25)
    batch = NoteEventBatch(events=(late, duplicate, duplicate, overlap))

    restored = deserialize_note_event_batch(serialize_note_event_batch(batch))

    assert restored == batch
    assert restored.events == (late, duplicate, duplicate, overlap)
    assert restored.events[1] is not restored.events[2]


@pytest.mark.parametrize(
    "payload",
    [
        "{",
        "not-json",
        "NaN",
        "[]",
        '"value"',
        "null",
    ],
)
def test_deserializer_rejects_malformed_or_non_object_roots(payload: str) -> None:
    with pytest.raises(InvalidNoteEventPayloadError):
        deserialize_note_event_batch(payload)


def test_deserializer_rejects_missing_and_unknown_root_fields() -> None:
    missing_version: dict[str, Any] = {"events": []}
    missing_events: dict[str, Any] = {"schema_version": "1.0"}
    unknown: dict[str, Any] = {
        "schema_version": "1.0",
        "events": [],
        "model": "future",
    }

    for document in (missing_version, missing_events, unknown):
        with pytest.raises(InvalidNoteEventPayloadError):
            deserialize_note_event_batch(json.dumps(document))


@pytest.mark.parametrize("version", ["2.0", "", 1, None, True])
def test_deserializer_uses_specific_error_for_unsupported_versions(version: Any) -> None:
    document = {"schema_version": version, "events": []}
    with pytest.raises(UnsupportedNoteEventSchemaVersionError):
        deserialize_note_event_batch(json.dumps(document))


@pytest.mark.parametrize("events", [{}, "events", 1, None, True])
def test_deserializer_requires_events_to_be_a_list(events: Any) -> None:
    document = {"schema_version": "1.0", "events": events}
    with pytest.raises(InvalidNoteEventPayloadError, match="events"):
        deserialize_note_event_batch(json.dumps(document))


def test_deserializer_rejects_non_object_event_with_index() -> None:
    document = {"schema_version": "1.0", "events": [valid_document()["events"][0], []]}
    with pytest.raises(InvalidNoteEventPayloadError, match="index 1") as captured:
        deserialize_note_event_batch(json.dumps(document))
    assert captured.value.event_index == 1


def test_deserializer_rejects_missing_event_field_with_index() -> None:
    document = valid_document()
    del document["events"][0]["velocity"]
    with pytest.raises(InvalidNoteEventPayloadError, match="index 0") as captured:
        deserialize_note_event_batch(json.dumps(document))
    assert captured.value.event_index == 0
    assert "velocity" in str(captured.value)


def test_deserializer_rejects_unknown_event_field_with_index() -> None:
    document = valid_document()
    document["events"][0]["source_model"] = "forbidden"
    with pytest.raises(InvalidNoteEventPayloadError, match="index 0") as captured:
        deserialize_note_event_batch(json.dumps(document))
    assert captured.value.event_index == 0
    assert "source_model" in str(captured.value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pitch_concert_midi", "60"),
        ("pitch_concert_midi", 60.0),
        ("onset_seconds", "0.0"),
        ("offset_seconds", "0.5"),
        ("velocity", "100"),
        ("velocity", 100.0),
        ("confidence", "0.92"),
        ("confidence", True),
        ("offset_seconds", 0.0),
    ],
)
def test_deserializer_does_not_coerce_invalid_event_values_and_reports_index(
    field: str,
    value: Any,
) -> None:
    document = valid_document()
    document["events"].insert(0, valid_document()["events"][0].copy())
    document["events"][1][field] = value

    with pytest.raises(InvalidNoteEventPayloadError, match="index 1") as captured:
        deserialize_note_event_batch(json.dumps(document))

    assert captured.value.event_index == 1
    assert field in str(captured.value)
    assert isinstance(captured.value.__cause__, InvalidNoteEventError)


def test_contract_modules_and_existing_runtime_remain_disconnected_from_models_and_audio() -> None:
    root = Path(__file__).resolve().parents[2]
    contract_sources = [
        (root / "src/saxo_ai/domain/note_events.py").read_text(encoding="utf-8").lower(),
        (root / "src/saxo_ai/application/note_event_serialization.py")
        .read_text(encoding="utf-8")
        .lower(),
    ]
    for source in contract_sources:
        for forbidden in ("fastapi", "ffmpeg", "subprocess", "tempfile", "pydantic"):
            assert forbidden not in source

    routes = (root / "src/saxo_ai/api/routes.py").read_text(encoding="utf-8")
    main = (root / "src/saxo_ai/main.py").read_text(encoding="utf-8")
    assert "NoteEvent" not in routes
    assert "NoteEvent" not in main
    assert "TranscriptionEngine" not in main
    assert "BasicPitch" not in main
    assert "checkpoint" not in main.lower()
    assert not (root / "src/saxo_ai/transcription").exists()
