from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import pytest

from saxo_ai.application.note_event_serialization import serialize_note_event_batch
from saxo_ai.application.written_pitch import TransposeWrittenPitchEvents
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.note_confidence import (
    ConfidenceAnnotatedNoteEvent,
    ConfidenceAnnotatedTranscriptionResult,
    LowConfidenceReport,
    LowConfidenceSettings,
)
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
from saxo_ai.domain.transposition import (
    InvalidSaxophoneTypeError,
    WrittenPitchOutOfRangeError,
)
from saxo_ai.domain.written_pitch import (
    WRITTEN_PITCH_POLICY_VERSION,
    InvalidWrittenPitchContractError,
    WrittenPitchNoteEvent,
    WrittenPitchTranscriptionResult,
)

ROOT = Path(__file__).resolve().parents[2]


def note(
    *,
    pitch: int,
    onset: float,
    confidence: float,
    velocity: int = 100,
) -> NoteEvent:
    return NoteEvent(
        pitch_concert_midi=pitch,
        onset_seconds=onset,
        offset_seconds=onset + 0.5,
        velocity=velocity,
        confidence=confidence,
    )


def annotated_result(
    events: tuple[NoteEvent, ...],
    markers: tuple[bool, ...],
) -> ConfidenceAnnotatedTranscriptionResult:
    batch = NoteEventBatch(events=events)
    raw = TranscriptionResult(
        notes=batch,
        model=TranscriptionModelIdentity(
            engine_name="filosax",
            engine_version="0.1.1",
            engine_source_revision="a" * 40,
            model_id="xavriley/midi-transcription-models",
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
    processed = PostProcessedTranscriptionResult(
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
    annotations = tuple(
        ConfidenceAnnotatedNoteEvent(event=event, is_low_confidence=marker)
        for event, marker in zip(events, markers, strict=True)
    )
    low_count = sum(markers)
    return ConfidenceAnnotatedTranscriptionResult(
        original=processed,
        annotated_events=annotations,
        report=LowConfidenceReport(
            settings=LowConfidenceSettings(),
            input_event_count=len(events),
            low_confidence_count=low_count,
            regular_confidence_count=len(events) - low_count,
        ),
    )


def test_written_pitch_policy_version_is_stable() -> None:
    assert WRITTEN_PITCH_POLICY_VERSION == "1.0"


def test_written_pitch_note_event_preserves_source_and_concert_event_reference() -> None:
    concert = note(pitch=60, onset=0.0, confidence=0.4)
    annotation = ConfidenceAnnotatedNoteEvent(event=concert, is_low_confidence=True)

    written = WrittenPitchNoteEvent(source=annotation, written_pitch_midi=69)

    assert written.source is annotation
    assert written.source.event is concert
    assert written.written_pitch_midi == 69
    assert written.source.event.pitch_concert_midi == 60


@pytest.mark.parametrize("written_pitch", [-1, 128, 60.0, True, False, "60", None])
def test_written_pitch_note_event_rejects_invalid_written_pitch(written_pitch: object) -> None:
    annotation = ConfidenceAnnotatedNoteEvent(
        event=note(pitch=60, onset=0.0, confidence=0.4),
        is_low_confidence=True,
    )

    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchNoteEvent(
            source=annotation,
            written_pitch_midi=cast(Any, written_pitch),
        )


def test_written_pitch_note_event_rejects_non_annotation_source() -> None:
    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchNoteEvent(source=cast(Any, object()), written_pitch_midi=60)


def test_written_pitch_note_event_is_immutable() -> None:
    annotation = ConfidenceAnnotatedNoteEvent(
        event=note(pitch=60, onset=0.0, confidence=0.4),
        is_low_confidence=True,
    )
    written = WrittenPitchNoteEvent(source=annotation, written_pitch_midi=69)

    with pytest.raises(FrozenInstanceError):
        written.source = annotation  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        written.written_pitch_midi = 70  # type: ignore[misc]


@pytest.mark.parametrize(
    ("saxophone_type", "expected"),
    [
        (SaxophoneType.SOPRANO, 62),
        (SaxophoneType.ALTO, 69),
        (SaxophoneType.TENOR, 74),
        (SaxophoneType.BARITONE, 81),
    ],
)
def test_use_case_transposes_concert_pitch_for_each_saxophone(
    saxophone_type: SaxophoneType,
    expected: int,
) -> None:
    concert = note(pitch=60, onset=0.0, confidence=0.4)
    original = annotated_result((concert,), (True,))

    result = TransposeWrittenPitchEvents().execute(original, saxophone_type)

    assert result.original is original
    assert result.saxophone_type is saxophone_type
    assert result.events[0].source is original.annotated_events[0]
    assert result.events[0].source.event is concert
    assert result.events[0].source.event.pitch_concert_midi == 60
    assert result.events[0].written_pitch_midi == expected


def test_use_case_accepts_empty_annotated_result() -> None:
    original = annotated_result((), ())

    result = TransposeWrittenPitchEvents().execute(original, SaxophoneType.ALTO)

    assert result.original is original
    assert result.events == ()
    assert result.policy_version == "1.0"


def test_use_case_preserves_count_order_confidence_and_markers() -> None:
    events = (
        note(pitch=72, onset=2.0, confidence=0.0, velocity=0),
        note(pitch=60, onset=0.0, confidence=1.0),
        note(pitch=67, onset=0.5, confidence=0.4),
    )
    original = annotated_result(events, (True, False, True))

    result = TransposeWrittenPitchEvents().execute(original, SaxophoneType.SOPRANO)

    assert len(result.events) == len(original.annotated_events) == 3
    assert tuple(item.source for item in result.events) == original.annotated_events
    assert [item.source.event.pitch_concert_midi for item in result.events] == [72, 60, 67]
    assert [item.written_pitch_midi for item in result.events] == [74, 62, 69]
    assert [item.source.event.onset_seconds for item in result.events] == [2.0, 0.0, 0.5]
    assert [item.source.event.confidence for item in result.events] == [0.0, 1.0, 0.4]
    assert [item.source.is_low_confidence for item in result.events] == [True, False, True]


def test_use_case_preserves_complete_provenance_chain() -> None:
    original = annotated_result(
        (note(pitch=60, onset=0.0, confidence=0.4),),
        (True,),
    )

    result = TransposeWrittenPitchEvents().execute(original, SaxophoneType.ALTO)

    assert result.original is original
    assert result.original.original is original.original
    assert result.original.original.original is original.original.original
    assert result.original.original.original.model is original.original.original.model
    assert result.original.original.original.settings is original.original.original.settings
    assert result.original.original.report is original.original.report
    assert result.original.report is original.report
    assert result.original.original.original.model.engine_version == "0.1.1"
    assert result.original.original.original.model.engine_source_revision == "a" * 40
    assert result.original.original.original.model.model_revision == "b" * 40
    assert result.original.original.original.model.checkpoint_filename == "filosax_25k.pth"


def test_use_case_fails_atomically_and_adds_failing_event_index() -> None:
    events = (
        note(pitch=60, onset=0.0, confidence=0.4),
        note(pitch=61, onset=0.6, confidence=0.8),
        note(pitch=119, onset=1.2, confidence=0.2),
    )
    original = annotated_result(events, (True, False, True))
    original_annotations = original.annotated_events

    with pytest.raises(WrittenPitchOutOfRangeError) as captured:
        TransposeWrittenPitchEvents().execute(original, SaxophoneType.ALTO)

    error = captured.value
    assert error.event_index == 2
    assert error.saxophone_type is SaxophoneType.ALTO
    assert error.concert_pitch_midi == 119
    assert error.written_offset_semitones == 9
    assert error.attempted_written_pitch_midi == 128
    assert original.annotated_events is original_annotations
    assert tuple(annotation.event for annotation in original.annotated_events) == events
    assert [event.pitch_concert_midi for event in events] == [60, 61, 119]


def test_use_case_rejects_non_saxophone_type_before_processing() -> None:
    original = annotated_result(
        (note(pitch=60, onset=0.0, confidence=0.4),),
        (True,),
    )

    with pytest.raises(InvalidSaxophoneTypeError):
        TransposeWrittenPitchEvents().execute(original, cast(Any, "alto"))


def test_use_case_rejects_non_annotated_original() -> None:
    with pytest.raises(InvalidWrittenPitchContractError):
        TransposeWrittenPitchEvents().execute(cast(Any, object()), SaxophoneType.ALTO)


def valid_written_result() -> WrittenPitchTranscriptionResult:
    original = annotated_result(
        (
            note(pitch=60, onset=0.0, confidence=0.4),
            note(pitch=67, onset=0.5, confidence=0.8),
        ),
        (True, False),
    )
    return WrittenPitchTranscriptionResult(
        original=original,
        saxophone_type=SaxophoneType.ALTO,
        events=(
            WrittenPitchNoteEvent(original.annotated_events[0], 69),
            WrittenPitchNoteEvent(original.annotated_events[1], 76),
        ),
    )


def test_written_pitch_result_is_immutable() -> None:
    result = valid_written_result()

    with pytest.raises(FrozenInstanceError):
        result.saxophone_type = SaxophoneType.TENOR  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.events = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.policy_version = "2.0"  # type: ignore[misc]


def test_written_pitch_result_rejects_event_count_mismatch() -> None:
    valid = valid_written_result()

    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchTranscriptionResult(
            original=valid.original,
            saxophone_type=SaxophoneType.ALTO,
            events=valid.events[:1],
        )


def test_written_pitch_result_rejects_different_source_reference() -> None:
    valid = valid_written_result()
    replacement = ConfidenceAnnotatedNoteEvent(
        event=valid.events[0].source.event,
        is_low_confidence=valid.events[0].source.is_low_confidence,
    )

    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchTranscriptionResult(
            original=valid.original,
            saxophone_type=SaxophoneType.ALTO,
            events=(
                WrittenPitchNoteEvent(replacement, 69),
                valid.events[1],
            ),
        )


def test_written_pitch_result_rejects_source_order_change() -> None:
    valid = valid_written_result()

    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchTranscriptionResult(
            original=valid.original,
            saxophone_type=SaxophoneType.ALTO,
            events=(valid.events[1], valid.events[0]),
        )


def test_written_pitch_result_rejects_incorrect_derived_pitch() -> None:
    valid = valid_written_result()

    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchTranscriptionResult(
            original=valid.original,
            saxophone_type=SaxophoneType.ALTO,
            events=(
                WrittenPitchNoteEvent(valid.events[0].source, 70),
                valid.events[1],
            ),
        )


def test_written_pitch_result_rejects_invalid_saxophone_type() -> None:
    valid = valid_written_result()

    with pytest.raises(InvalidSaxophoneTypeError):
        WrittenPitchTranscriptionResult(
            original=valid.original,
            saxophone_type=cast(Any, "alto"),
            events=valid.events,
        )


def test_written_pitch_result_rejects_unsupported_policy_version() -> None:
    valid = valid_written_result()

    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchTranscriptionResult(
            original=valid.original,
            saxophone_type=SaxophoneType.ALTO,
            events=valid.events,
            policy_version="2.0",
        )


def test_original_note_event_schema_and_serializer_remain_unchanged() -> None:
    event = note(pitch=60, onset=0.0, confidence=0.4)
    payload = serialize_note_event_batch(NoteEventBatch(events=(event,)))

    assert NOTE_EVENT_SCHEMA_VERSION == "1.0"
    assert NOTE_EVENT_FIELDS == (
        "pitch_concert_midi",
        "onset_seconds",
        "offset_seconds",
        "velocity",
        "confidence",
    )
    assert "written_pitch" not in payload
    assert "is_low_confidence" not in payload


def test_written_pitch_modules_do_not_import_forbidden_dependencies() -> None:
    source = "\n".join(
        (
            (ROOT / "src/saxo_ai/domain/transposition.py").read_text(),
            (ROOT / "src/saxo_ai/domain/written_pitch.py").read_text(),
            (ROOT / "src/saxo_ai/application/written_pitch.py").read_text(),
        )
    )

    for forbidden in (
        "fastapi",
        "torch",
        "huggingface_hub",
        "hf_midi_transcription",
        "piano_transcription_inference",
        "subprocess",
        "tempfile",
        "mido",
    ):
        assert forbidden not in source


def test_written_pitch_result_rejects_non_annotated_original() -> None:
    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchTranscriptionResult(
            original=cast(Any, object()),
            saxophone_type=SaxophoneType.ALTO,
            events=(),
        )


def test_written_pitch_result_rejects_non_tuple_events() -> None:
    original = annotated_result((), ())

    with pytest.raises(InvalidWrittenPitchContractError):
        WrittenPitchTranscriptionResult(
            original=original,
            saxophone_type=SaxophoneType.ALTO,
            events=cast(Any, []),
        )
