from __future__ import annotations

import json

from saxo_ai.domain.note_confidence import (
    CONFIDENCE_INTERPRETATION,
    LOW_CONFIDENCE_VIEW_SCHEMA_VERSION,
    ConfidenceAnnotatedNoteEvent,
    ConfidenceAnnotatedTranscriptionResult,
)
from saxo_ai.domain.note_events import NOTE_EVENT_FIELDS


def serialize_confidence_annotated_result(
    result: ConfidenceAnnotatedTranscriptionResult,
) -> str:
    """Serialize the deterministic, output-only confidence review view."""

    document = {
        "schema_version": LOW_CONFIDENCE_VIEW_SCHEMA_VERSION,
        "policy_version": result.report.settings.policy_version,
        "low_confidence_threshold": result.report.settings.low_confidence_threshold,
        "confidence_interpretation": CONFIDENCE_INTERPRETATION,
        "confidence_method": result.original.original.settings.confidence_method,
        "summary": {
            "event_count": result.report.input_event_count,
            "low_confidence_count": result.report.low_confidence_count,
        },
        "events": [_serialize_annotation(annotation) for annotation in result.annotated_events],
    }
    return json.dumps(
        document,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )


def _serialize_annotation(
    annotation: ConfidenceAnnotatedNoteEvent,
) -> dict[str, object]:
    event_document: dict[str, object] = {
        field_name: getattr(annotation.event, field_name) for field_name in NOTE_EVENT_FIELDS
    }
    event_document["is_low_confidence"] = annotation.is_low_confidence
    return event_document
