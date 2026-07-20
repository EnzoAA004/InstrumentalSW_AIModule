from __future__ import annotations

import json
from pathlib import Path

from saxo_ai.application.note_event_postprocessing import PostProcessTranscriptionEvents
from saxo_ai.application.note_event_serialization import (
    deserialize_note_event_batch,
    serialize_note_event_batch,
)
from saxo_ai.domain.note_event_postprocessing import NoteEventPostProcessingSettings
from saxo_ai.domain.note_events import NOTE_EVENT_SCHEMA_VERSION, NoteEvent, NoteEventBatch
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)


def note(
    *,
    pitch: int = 60,
    onset: float = 0.0,
    offset: float = 0.5,
    velocity: int = 90,
    confidence: float = 0.8,
) -> NoteEvent:
    return NoteEvent(
        pitch_concert_midi=pitch,
        onset_seconds=onset,
        offset_seconds=offset,
        velocity=velocity,
        confidence=confidence,
    )


def raw_result(*events: NoteEvent) -> TranscriptionResult:
    return TranscriptionResult(
        notes=NoteEventBatch(events=events),
        model=TranscriptionModelIdentity(
            engine_name="hf-midi-transcription",
            engine_version="0.1.1",
            engine_source_revision="a" * 40,
            model_id="xavriley/midi-transcription-models",
            model_revision="model-revision",
            checkpoint_filename="filosax_25k.pth",
            checkpoint_sha256="b" * 64,
        ),
        settings=TranscriptionSettings(
            sample_rate_hz=16000,
            device="cpu",
            onset_threshold=0.3,
            offset_threshold=0.3,
            frame_threshold=0.1,
            confidence_method="activation_mean",
        ),
    )


def test_empty_batch_is_no_op_with_zero_report() -> None:
    original = raw_result()

    processed = PostProcessTranscriptionEvents().execute(original)

    assert processed.original is original
    assert processed.notes is original.notes
    assert processed.report.input_event_count == 0
    assert processed.report.output_event_count == 0
    assert processed.report.affected_event_count == 0


def test_zero_threshold_preserves_every_valid_non_duplicate_event() -> None:
    event = note(onset=0.0, offset=0.000001)
    original = raw_result(event)

    processed = PostProcessTranscriptionEvents(
        settings=NoteEventPostProcessingSettings(minimum_duration_seconds=0.0)
    ).execute(original)

    assert processed.notes is original.notes
    assert processed.notes.events[0] is event


def test_event_below_minimum_duration_is_removed() -> None:
    short = note(onset=0.0, offset=0.029999)

    processed = PostProcessTranscriptionEvents().execute(raw_result(short))

    assert processed.notes.events == ()
    assert processed.report.short_duration_removed_count == 1
    assert processed.report.duplicate_removed_count == 0


def test_event_exactly_at_threshold_is_preserved_without_recreation() -> None:
    threshold = 0.030
    boundary = note(onset=0.0, offset=threshold)
    assert boundary.duration_seconds == threshold
    original = raw_result(boundary)

    processed = PostProcessTranscriptionEvents().execute(original)

    assert processed.notes is original.notes
    assert processed.notes.events[0] is boundary


def test_event_above_threshold_is_preserved_without_recreation() -> None:
    event = note(offset=0.030001)
    original = raw_result(event)

    processed = PostProcessTranscriptionEvents().execute(original)

    assert processed.notes is original.notes
    assert processed.notes.events[0] is event


def test_identical_duplicate_objects_reduce_to_one_event() -> None:
    first = note()
    second = note()

    processed = PostProcessTranscriptionEvents().execute(raw_result(first, second))

    assert processed.notes.events == (first,)
    assert processed.notes.events[0] is first
    assert processed.report.duplicate_removed_count == 1
    assert processed.report.duplicate_group_count == 1


def test_same_object_reference_twice_reduces_to_one_reference() -> None:
    event = note()

    processed = PostProcessTranscriptionEvents().execute(raw_result(event, event))

    assert processed.notes.events == (event,)
    assert processed.notes.events[0] is event


def test_higher_confidence_duplicate_is_kept_exactly() -> None:
    lower = note(confidence=0.4, velocity=127)
    higher = note(confidence=0.8, velocity=1)

    processed = PostProcessTranscriptionEvents().execute(raw_result(lower, higher))

    assert processed.notes.events == (higher,)
    assert processed.notes.events[0] is higher


def test_higher_velocity_breaks_confidence_tie() -> None:
    lower = note(confidence=0.8, velocity=70)
    higher = note(confidence=0.8, velocity=100)

    processed = PostProcessTranscriptionEvents().execute(raw_result(lower, higher))

    assert processed.notes.events[0] is higher


def test_first_appearance_breaks_total_tie() -> None:
    first = note(confidence=0.8, velocity=100)
    second = note(confidence=0.8, velocity=100)

    processed = PostProcessTranscriptionEvents().execute(raw_result(first, second))

    assert processed.notes.events[0] is first


def test_three_duplicates_report_two_removed_in_one_group() -> None:
    events = (note(confidence=0.2), note(confidence=0.9), note(confidence=0.4))

    processed = PostProcessTranscriptionEvents().execute(raw_result(*events))

    assert processed.notes.events == (events[1],)
    assert processed.report.input_event_count == 3
    assert processed.report.output_event_count == 1
    assert processed.report.duplicate_removed_count == 2
    assert processed.report.duplicate_group_count == 1


def test_multiple_duplicate_groups_report_groups_independently() -> None:
    c1 = note(pitch=60, confidence=0.3)
    c2 = note(pitch=60, confidence=0.9)
    d1 = note(pitch=62, confidence=0.4)
    d2 = note(pitch=62, confidence=0.5)
    d3 = note(pitch=62, confidence=0.6)

    processed = PostProcessTranscriptionEvents().execute(raw_result(c1, d1, c2, d2, d3))

    assert processed.notes.events == (c2, d3)
    assert processed.report.duplicate_removed_count == 3
    assert processed.report.duplicate_group_count == 2


def test_tiny_time_difference_is_not_an_approximate_duplicate() -> None:
    first = note(onset=0.0, offset=0.5)
    second = note(onset=0.0, offset=0.5000000000000001)
    original = raw_result(first, second)

    processed = PostProcessTranscriptionEvents().execute(original)

    assert processed.notes is original.notes
    assert processed.notes.events == (first, second)


def test_same_pitch_with_different_onset_is_preserved() -> None:
    first = note(onset=0.0, offset=0.5)
    second = note(onset=0.1, offset=0.5)

    processed = PostProcessTranscriptionEvents().execute(raw_result(first, second))

    assert processed.notes.events == (first, second)


def test_different_pitch_with_same_interval_is_preserved() -> None:
    first = note(pitch=60)
    second = note(pitch=61)

    processed = PostProcessTranscriptionEvents().execute(raw_result(first, second))

    assert processed.notes.events == (first, second)


def test_overlapping_non_duplicate_events_are_preserved() -> None:
    first = note(pitch=60, onset=0.0, offset=0.5)
    second = note(pitch=64, onset=0.25, offset=0.75)

    processed = PostProcessTranscriptionEvents().execute(raw_result(first, second))

    assert processed.notes.events == (first, second)


def test_zero_confidence_and_zero_velocity_are_not_filtered() -> None:
    event = note(confidence=0.0, velocity=0)
    original = raw_result(event)

    processed = PostProcessTranscriptionEvents().execute(original)

    assert processed.notes is original.notes
    assert processed.notes.events[0] is event


def test_short_duplicates_are_only_counted_as_short_duration_removals() -> None:
    first = note(offset=0.02, confidence=0.2)
    second = note(offset=0.02, confidence=0.9)

    processed = PostProcessTranscriptionEvents().execute(raw_result(first, second))

    assert processed.notes.events == ()
    assert processed.report.short_duration_removed_count == 2
    assert processed.report.duplicate_removed_count == 0
    assert processed.report.duplicate_group_count == 0
    assert processed.report.affected_event_count == 2


def test_winning_late_duplicate_occupies_first_group_position() -> None:
    early = note(pitch=60, confidence=0.4)
    independent = note(pitch=67, onset=0.1, offset=0.6, confidence=0.7)
    winner = note(pitch=60, confidence=0.8)

    processed = PostProcessTranscriptionEvents().execute(raw_result(early, independent, winner))

    assert processed.notes.events == (winner, independent)
    assert processed.notes.events[0] is winner
    assert processed.notes.events[1] is independent


def test_no_op_preserves_original_batch_identity_and_provenance() -> None:
    first = note(pitch=67, onset=0.5, offset=1.0)
    second = note(pitch=60, onset=0.0, offset=0.5)
    original = raw_result(first, second)
    model = original.model
    settings = original.settings

    processed = PostProcessTranscriptionEvents().execute(original)

    assert processed.original is original
    assert processed.notes is original.notes
    assert processed.original.model is model
    assert processed.original.settings is settings
    assert processed.original.model.engine_version == "0.1.1"
    assert processed.original.model.engine_source_revision == "a" * 40
    assert processed.original.model.model_revision == "model-revision"
    assert processed.original.model.checkpoint_filename == "filosax_25k.pth"
    assert processed.report.input_event_count == processed.report.output_event_count == 2
    assert processed.report.affected_event_count == 0


def test_processed_batch_uses_existing_json_codec_and_schema_one() -> None:
    lower = note(confidence=0.4)
    higher = note(confidence=0.8)

    processed = PostProcessTranscriptionEvents().execute(raw_result(lower, higher))
    payload = serialize_note_event_batch(processed.notes)
    restored = deserialize_note_event_batch(payload)
    document = json.loads(payload)

    assert restored == processed.notes
    assert restored.schema_version == NOTE_EVENT_SCHEMA_VERSION == "1.0"
    assert set(document) == {"schema_version", "events"}
    assert "report" not in document
    assert "policy_version" not in document


def test_postprocessor_has_no_forbidden_runtime_or_api_imports() -> None:
    root = Path(__file__).parents[2]
    source = (root / "src/saxo_ai/application/note_event_postprocessing.py").read_text()
    domain = (root / "src/saxo_ai/domain/note_event_postprocessing.py").read_text()
    forbidden = (
        "fastapi",
        "torch",
        "huggingface_hub",
        "hf_midi_transcription",
        "piano_transcription_inference",
        "subprocess",
        "tempfile",
    )

    assert all(name not in source for name in forbidden)
    assert all(name not in domain for name in forbidden)
