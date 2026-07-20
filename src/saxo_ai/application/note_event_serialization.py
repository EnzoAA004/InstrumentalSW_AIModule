from __future__ import annotations

import json
from typing import Any

from saxo_ai.domain.note_events import (
    NOTE_EVENT_FIELDS,
    NOTE_EVENT_SCHEMA_VERSION,
    InvalidNoteEventError,
    NoteEvent,
    NoteEventBatch,
    UnsupportedNoteEventSchemaVersionError,
)

_ROOT_FIELDS = frozenset(("schema_version", "events"))
_EVENT_FIELDS = frozenset(NOTE_EVENT_FIELDS)


class InvalidNoteEventPayloadError(ValueError):
    """Raised when a JSON payload does not match the NoteEvent batch contract."""

    def __init__(self, message: str, *, event_index: int | None = None) -> None:
        if event_index is None:
            rendered = message
        else:
            rendered = f"Invalid event at index {event_index}: {message}"
        super().__init__(rendered)
        self.event_index = event_index


def serialize_note_event_batch(batch: NoteEventBatch) -> str:
    """Serialize a validated batch to deterministic schema-versioned JSON."""

    document = {
        "schema_version": batch.schema_version,
        "events": [_serialize_event(event) for event in batch.events],
    }
    return json.dumps(
        document,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )


def _serialize_event(event: NoteEvent) -> dict[str, object]:
    return {field_name: getattr(event, field_name) for field_name in NOTE_EVENT_FIELDS}


def deserialize_note_event_batch(payload: str) -> NoteEventBatch:
    """Read strict JSON and rebuild the domain contract without coercion."""

    if not isinstance(payload, str):
        raise InvalidNoteEventPayloadError("payload must be a JSON string")
    try:
        document = json.loads(payload, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as error:
        raise InvalidNoteEventPayloadError("payload is not valid JSON") from error

    if not isinstance(document, dict):
        raise InvalidNoteEventPayloadError("payload root must be an object")
    _validate_root_fields(document)

    schema_version = document["schema_version"]
    if schema_version != NOTE_EVENT_SCHEMA_VERSION:
        raise UnsupportedNoteEventSchemaVersionError(schema_version)

    raw_events = document["events"]
    if not isinstance(raw_events, list):
        raise InvalidNoteEventPayloadError("events must be a list")

    events = tuple(
        _deserialize_event(raw_event, index) for index, raw_event in enumerate(raw_events)
    )
    return NoteEventBatch(events=events, schema_version=schema_version)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not supported")


def _validate_root_fields(document: dict[str, Any]) -> None:
    actual = set(document)
    missing = _ROOT_FIELDS - actual
    unknown = actual - _ROOT_FIELDS
    if missing:
        raise InvalidNoteEventPayloadError(
            f"missing required root field(s): {', '.join(sorted(missing))}"
        )
    if unknown:
        raise InvalidNoteEventPayloadError(f"unknown root field(s): {', '.join(sorted(unknown))}")


def _deserialize_event(raw_event: object, index: int) -> NoteEvent:
    if not isinstance(raw_event, dict):
        raise InvalidNoteEventPayloadError(
            "event must be an object",
            event_index=index,
        )
    actual = set(raw_event)
    missing = _EVENT_FIELDS - actual
    unknown = actual - _EVENT_FIELDS
    if missing:
        raise InvalidNoteEventPayloadError(
            f"missing required field(s): {', '.join(sorted(missing))}",
            event_index=index,
        )
    if unknown:
        raise InvalidNoteEventPayloadError(
            f"unknown field(s): {', '.join(sorted(unknown))}",
            event_index=index,
        )

    try:
        return NoteEvent(
            pitch_concert_midi=raw_event["pitch_concert_midi"],
            onset_seconds=raw_event["onset_seconds"],
            offset_seconds=raw_event["offset_seconds"],
            velocity=raw_event["velocity"],
            confidence=raw_event["confidence"],
        )
    except InvalidNoteEventError as error:
        raise InvalidNoteEventPayloadError(str(error), event_index=index) from error
