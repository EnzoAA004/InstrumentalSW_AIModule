import inspect
import json

from saxo_ai.application.note_confidence import MarkLowConfidenceEvents
from saxo_ai.application.note_confidence_serialization import serialize_confidence_annotated_result
from saxo_ai.application.note_event_serialization import serialize_note_event_batch
from saxo_ai.domain.note_confidence import CONFIDENCE_INTERPRETATION
from saxo_ai.domain.note_event_postprocessing import (
    NoteEventPostProcessingReport,
    NoteEventPostProcessingSettings,
    PostProcessedTranscriptionResult,
)
from saxo_ai.domain.note_events import (
    NOTE_EVENT_FIELDS,
    NOTE_EVENT_SCHEMA_VERSION,
    NoteEvent,
    NoteEventBatch,
)
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)


def make_processed(events: tuple[NoteEvent, ...]) -> PostProcessedTranscriptionResult:
    batch = NoteEventBatch(events=events)
    raw = TranscriptionResult(
        notes=batch,
        model=TranscriptionModelIdentity(
            engine_name="filosax",
            engine_version="0.1.1",
            engine_source_revision="a" * 40,
            model_id="model",
            model_revision="b" * 40,
            checkpoint_filename="filosax_25k.pth",
            checkpoint_sha256="c" * 64,
        ),
        settings=TranscriptionSettings(
            sample_rate_hz=16000,
            device="cpu",
            onset_threshold=0.3,
            offset_threshold=0.3,
            frame_threshold=0.1,
            confidence_method="max_reg_onset_activation_pm2_frames",
        ),
    )
    return PostProcessedTranscriptionResult(
        original=raw,
        notes=batch,
        report=NoteEventPostProcessingReport(
            settings=NoteEventPostProcessingSettings(),
            input_event_count=len(events),
            output_event_count=len(events),
            short_duration_removed_count=0,
            duplicate_removed_count=0,
            duplicate_group_count=0,
        ),
    )


def test_serialization_has_exact_versioned_root_and_event_shape() -> None:
    events = (
        NoteEvent(60, 0.0, 0.5, 100, 0.4),
        NoteEvent(67, 0.1, 0.6, 90, 0.7),
    )
    result = MarkLowConfidenceEvents().execute(make_processed(events))

    payload = json.loads(serialize_confidence_annotated_result(result))

    assert set(payload) == {
        "schema_version",
        "policy_version",
        "low_confidence_threshold",
        "confidence_interpretation",
        "confidence_method",
        "summary",
        "events",
    }
    assert payload["schema_version"] == "1.0"
    assert payload["policy_version"] == "1.0"
    assert payload["low_confidence_threshold"] == 0.5
    assert payload["confidence_interpretation"] == CONFIDENCE_INTERPRETATION
    assert payload["confidence_method"] == "max_reg_onset_activation_pm2_frames"
    assert payload["summary"] == {"event_count": 2, "low_confidence_count": 1}
    assert set(payload["events"][0]) == {*NOTE_EVENT_FIELDS, "is_low_confidence"}
    assert payload["events"][0] == {
        "pitch_concert_midi": 60,
        "onset_seconds": 0.0,
        "offset_seconds": 0.5,
        "velocity": 100,
        "confidence": 0.4,
        "is_low_confidence": True,
    }
    assert type(payload["events"][0]["is_low_confidence"]) is bool


def test_serialization_preserves_order_and_original_values() -> None:
    first = NoteEvent(72, 2.0, 2.5, 0, 0.8)
    second = NoteEvent(60, 0.0, 0.5, 127, 0.2)
    result = MarkLowConfidenceEvents().execute(make_processed((first, second)))

    payload = json.loads(serialize_confidence_annotated_result(result))

    assert [item["pitch_concert_midi"] for item in payload["events"]] == [72, 60]
    assert payload["events"][0]["velocity"] == 0
    assert payload["events"][0]["confidence"] == 0.8
    assert payload["events"][1]["confidence"] == 0.2


def test_serialization_is_deterministic_and_compact() -> None:
    result = MarkLowConfidenceEvents().execute(
        make_processed((NoteEvent(60, 0.0, 0.5, 100, 0.4),))
    )

    first = serialize_confidence_annotated_result(result)
    second = serialize_confidence_annotated_result(result)

    assert first == second
    assert ": " not in first
    assert ", " not in first


def test_serialization_omits_accuracy_probability_wrong_and_sax022_report_fields() -> None:
    result = MarkLowConfidenceEvents().execute(
        make_processed((NoteEvent(60, 0.0, 0.5, 100, 0.4),))
    )

    payload = json.loads(serialize_confidence_annotated_result(result))

    root_and_event_keys = set(payload) | set(payload["summary"])
    root_and_event_keys.update(key for event in payload["events"] for key in event)
    for forbidden in (
        "accuracy",
        "probability_correct",
        "probability_incorrect",
        "is_wrong",
        "is_inaccurate",
        "short_duration_removed_count",
        "duplicate_removed_count",
        "duplicate_group_count",
    ):
        assert forbidden not in root_and_event_keys


def test_serialization_supports_empty_batch() -> None:
    result = MarkLowConfidenceEvents().execute(make_processed(()))

    payload = json.loads(serialize_confidence_annotated_result(result))

    assert payload["events"] == []
    assert payload["summary"] == {"event_count": 0, "low_confidence_count": 0}


def test_original_note_event_schema_and_serializer_remain_unchanged() -> None:
    batch = NoteEventBatch(events=(NoteEvent(60, 0.0, 0.5, 100, 0.4),))

    original_payload = serialize_note_event_batch(batch)

    assert NOTE_EVENT_SCHEMA_VERSION == "1.0"
    assert NOTE_EVENT_FIELDS == (
        "pitch_concert_midi",
        "onset_seconds",
        "offset_seconds",
        "velocity",
        "confidence",
    )
    assert "is_low_confidence" not in original_payload
    assert json.loads(original_payload)["events"][0] == {
        "pitch_concert_midi": 60,
        "onset_seconds": 0.0,
        "offset_seconds": 0.5,
        "velocity": 100,
        "confidence": 0.4,
    }


def test_new_modules_do_not_import_forbidden_framework_or_runtime_dependencies() -> None:
    from saxo_ai.application import note_confidence, note_confidence_serialization
    from saxo_ai.domain import note_confidence as note_confidence_domain

    source = "\n".join(
        inspect.getsource(module)
        for module in (note_confidence_domain, note_confidence, note_confidence_serialization)
    )

    for forbidden in (
        "fastapi",
        "torch",
        "huggingface_hub",
        "hf_midi_transcription",
        "piano_transcription_inference",
        "subprocess",
        "tempfile",
    ):
        assert forbidden not in source
