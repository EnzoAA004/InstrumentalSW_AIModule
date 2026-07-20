import pytest

from saxo_ai.application.note_confidence import MarkLowConfidenceEvents
from saxo_ai.domain.note_confidence import (
    ConfidenceAnnotatedNoteEvent,
    ConfidenceAnnotatedTranscriptionResult,
    InvalidLowConfidenceContractError,
    LowConfidenceReport,
    LowConfidenceSettings,
)
from saxo_ai.domain.note_event_postprocessing import (
    NoteEventPostProcessingReport,
    NoteEventPostProcessingSettings,
    PostProcessedTranscriptionResult,
)
from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)


def make_event(
    *,
    pitch: int,
    onset: float,
    offset: float,
    confidence: float,
    velocity: int = 100,
) -> NoteEvent:
    return NoteEvent(
        pitch_concert_midi=pitch,
        onset_seconds=onset,
        offset_seconds=offset,
        velocity=velocity,
        confidence=confidence,
    )


def make_processed(events: tuple[NoteEvent, ...]) -> PostProcessedTranscriptionResult:
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
    report = NoteEventPostProcessingReport(
        settings=NoteEventPostProcessingSettings(),
        input_event_count=len(events),
        output_event_count=len(events),
        short_duration_removed_count=0,
        duplicate_removed_count=0,
        duplicate_group_count=0,
    )
    return PostProcessedTranscriptionResult(original=raw, notes=batch, report=report)


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [(0.499999, True), (0.50, False), (0.500001, False)],
)
def test_marking_uses_strict_threshold(confidence: float, expected: bool) -> None:
    event = make_event(pitch=60, onset=0.0, offset=0.5, confidence=confidence)
    processed = make_processed((event,))

    result = MarkLowConfidenceEvents().execute(processed)

    assert result.annotated_events[0].event is event
    assert result.annotated_events[0].is_low_confidence is expected


def test_zero_threshold_marks_no_valid_event() -> None:
    events = (
        make_event(pitch=60, onset=0.0, offset=0.5, confidence=0.0),
        make_event(pitch=61, onset=0.6, offset=1.0, confidence=1.0),
    )

    result = MarkLowConfidenceEvents(
        settings=LowConfidenceSettings(low_confidence_threshold=0.0)
    ).execute(make_processed(events))

    assert [item.is_low_confidence for item in result.annotated_events] == [False, False]


def test_one_threshold_marks_below_one_but_not_exactly_one() -> None:
    events = (
        make_event(pitch=60, onset=0.0, offset=0.5, confidence=0.0),
        make_event(pitch=61, onset=0.6, offset=1.0, confidence=0.999999),
        make_event(pitch=62, onset=1.1, offset=1.5, confidence=1.0),
    )

    result = MarkLowConfidenceEvents(
        settings=LowConfidenceSettings(low_confidence_threshold=1.0)
    ).execute(make_processed(events))

    assert [item.is_low_confidence for item in result.annotated_events] == [True, True, False]


def test_empty_batch_produces_empty_annotations_and_zero_report() -> None:
    processed = make_processed(())

    result = MarkLowConfidenceEvents().execute(processed)

    assert result.original is processed
    assert result.annotated_events == ()
    assert result.report.input_event_count == 0
    assert result.report.low_confidence_count == 0
    assert result.report.regular_confidence_count == 0
    assert result.report.affected_event_count == 0


def test_marking_preserves_all_event_references_order_and_count() -> None:
    events = (
        make_event(pitch=72, onset=2.0, offset=2.5, confidence=0.2),
        make_event(pitch=60, onset=0.0, offset=1.0, confidence=0.8, velocity=0),
        make_event(pitch=67, onset=0.5, offset=1.5, confidence=0.0),
    )
    processed = make_processed(events)

    result = MarkLowConfidenceEvents().execute(processed)

    assert result.original is processed
    assert len(result.annotated_events) == len(events)
    assert tuple(annotation.event for annotation in result.annotated_events) == events
    assert all(
        annotation.event is events[index]
        for index, annotation in enumerate(result.annotated_events)
    )
    assert [annotation.is_low_confidence for annotation in result.annotated_events] == [
        True,
        False,
        True,
    ]


def test_marking_preserves_complete_provenance_and_sax022_report() -> None:
    event = make_event(pitch=60, onset=0.0, offset=0.5, confidence=0.4)
    processed = make_processed((event,))

    result = MarkLowConfidenceEvents().execute(processed)

    assert result.original is processed
    assert result.original.original.model is processed.original.model
    assert result.original.original.model.engine_source_revision == "a" * 40
    assert result.original.original.model.model_revision == "b" * 40
    assert result.original.original.model.checkpoint_filename == "filosax_25k.pth"
    assert result.original.original.settings is processed.original.settings
    assert result.original.original.notes is processed.original.notes
    assert result.original.notes is processed.notes
    assert result.original.report is processed.report


def test_report_counts_marked_and_regular_without_removing_events() -> None:
    events = (
        make_event(pitch=60, onset=0.0, offset=0.5, confidence=0.1),
        make_event(pitch=61, onset=0.6, offset=1.0, confidence=0.5),
        make_event(pitch=62, onset=1.1, offset=1.5, confidence=0.9),
    )

    result = MarkLowConfidenceEvents().execute(make_processed(events))

    assert result.report.input_event_count == 3
    assert result.report.low_confidence_count == 1
    assert result.report.regular_confidence_count == 2
    assert result.report.affected_event_count == 1
    assert len(result.annotated_events) == 3


def test_result_rejects_annotation_count_mismatch() -> None:
    processed = make_processed((make_event(pitch=60, onset=0.0, offset=0.5, confidence=0.4),))
    report = LowConfidenceReport(
        settings=LowConfidenceSettings(),
        input_event_count=1,
        low_confidence_count=1,
        regular_confidence_count=0,
    )

    with pytest.raises(InvalidLowConfidenceContractError):
        ConfidenceAnnotatedTranscriptionResult(
            original=processed,
            annotated_events=(),
            report=report,
        )


def test_result_rejects_annotation_with_different_event_reference() -> None:
    source = make_event(pitch=60, onset=0.0, offset=0.5, confidence=0.4)
    replacement = make_event(pitch=60, onset=0.0, offset=0.5, confidence=0.4)
    processed = make_processed((source,))
    report = LowConfidenceReport(
        settings=LowConfidenceSettings(),
        input_event_count=1,
        low_confidence_count=1,
        regular_confidence_count=0,
    )

    with pytest.raises(InvalidLowConfidenceContractError):
        ConfidenceAnnotatedTranscriptionResult(
            original=processed,
            annotated_events=(
                ConfidenceAnnotatedNoteEvent(event=replacement, is_low_confidence=True),
            ),
            report=report,
        )


def test_result_rejects_non_postprocessed_original() -> None:
    report = LowConfidenceReport(
        settings=LowConfidenceSettings(),
        input_event_count=0,
        low_confidence_count=0,
        regular_confidence_count=0,
    )

    with pytest.raises(InvalidLowConfidenceContractError):
        ConfidenceAnnotatedTranscriptionResult(
            original=object(),  # type: ignore[arg-type]
            annotated_events=(),
            report=report,
        )
