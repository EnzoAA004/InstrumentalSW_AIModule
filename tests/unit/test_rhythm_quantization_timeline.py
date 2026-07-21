from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Any, cast

import pytest

from saxo_ai.application.rhythm_quantization import QuantizeMonophonicRhythm
from saxo_ai.application.tempo_resolution import ConfigureManualTempo
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
from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.rhythm_quantization import (
    InvalidQuantizedRhythmResultError,
    QuantizedNoteEvent,
    QuantizedRest,
    QuantizedRhythmResult,
    RhythmQuantizationReport,
    RhythmQuantizationSettings,
)
from saxo_ai.domain.tempo import TempoResolution
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent, WrittenPitchTranscriptionResult


def written_result(
    specs: tuple[tuple[int, float, float, float, bool], ...],
) -> WrittenPitchTranscriptionResult:
    notes = tuple(
        NoteEvent(pitch, onset, offset, 100 - index, confidence)
        for index, (pitch, onset, offset, confidence, _is_low) in enumerate(specs)
    )
    batch = NoteEventBatch(notes)
    raw = TranscriptionResult(
        batch,
        TranscriptionModelIdentity(
            "filosax",
            "0.1.1",
            "a" * 40,
            "model",
            "b" * 40,
            "filosax_25k.pth",
            "c" * 64,
        ),
        TranscriptionSettings(16_000, "cpu", 0.3, 0.3, 0.1, "activation"),
    )
    processed = PostProcessedTranscriptionResult(
        raw,
        batch,
        NoteEventPostProcessingReport(
            NoteEventPostProcessingSettings(),
            len(notes),
            len(notes),
            0,
            0,
            0,
        ),
    )
    annotations = tuple(
        ConfidenceAnnotatedNoteEvent(note, specs[index][4]) for index, note in enumerate(notes)
    )
    low_count = sum(annotation.is_low_confidence for annotation in annotations)
    annotated = ConfidenceAnnotatedTranscriptionResult(
        processed,
        annotations,
        LowConfidenceReport(
            LowConfidenceSettings(),
            len(notes),
            low_count,
            len(notes) - low_count,
        ),
    )
    return WrittenPitchTranscriptionResult(
        annotated,
        SaxophoneType.ALTO,
        tuple(
            WrittenPitchNoteEvent(annotation, annotation.event.pitch_concert_midi + 9)
            for annotation in annotations
        ),
    )


def manual_resolution(
    specs: tuple[tuple[int, float, float, float, bool], ...],
    *,
    bpm: float = 120.0,
) -> TempoResolution:
    return ConfigureManualTempo().execute(written_result(specs), bpm)


ROOT = Path(__file__).resolve().parents[2]


def quantize(
    specs: tuple[tuple[int, float, float, float, bool], ...],
    *,
    bpm: float = 120.0,
) -> QuantizedRhythmResult:
    return QuantizeMonophonicRhythm().execute(
        manual_resolution(specs, bpm=bpm),
        RhythmQuantizationSettings(),
    )


def test_initial_and_internal_gaps_become_explicit_rests_without_final_rest() -> None:
    result = quantize(
        (
            (60, 0.25, 0.50, 0.8, False),
            (62, 0.75, 1.00, 0.8, False),
        )
    )

    assert result.timeline == (
        QuantizedRest(0, 2),
        cast(QuantizedNoteEvent, result.timeline[1]),
        QuantizedRest(4, 6),
        cast(QuantizedNoteEvent, result.timeline[3]),
    )
    assert isinstance(result.timeline[-1], QuantizedNoteEvent)
    assert result.report.rest_count == 2


def test_adjacent_notes_do_not_create_rest() -> None:
    result = quantize(
        (
            (60, 0.0, 0.25, 0.8, False),
            (62, 0.25, 0.50, 0.8, False),
        )
    )

    assert all(not isinstance(item, QuantizedRest) for item in result.timeline)
    assert result.report.rest_count == 0


def test_real_gap_collapsing_to_same_grid_boundary_creates_no_zero_rest() -> None:
    result = quantize(
        (
            (60, 0.0, 0.249, 0.8, False),
            (62, 0.251, 0.50, 0.8, False),
        )
    )

    assert all(not isinstance(item, QuantizedRest) for item in result.timeline)


def test_empty_input_produces_empty_timeline_and_zero_report() -> None:
    result = quantize(())

    assert result.timeline == ()
    assert result.report.input_event_count == 0
    assert result.report.quantized_note_count == 0
    assert result.report.rest_count == 0
    assert result.report.total_absolute_timing_delta_seconds == 0.0
    assert result.report.maximum_absolute_boundary_delta_seconds == 0.0


def test_unsorted_input_keeps_original_order_and_references_but_timeline_is_chronological() -> None:
    tempo = manual_resolution(
        (
            (64, 0.50, 0.75, 0.8, False),
            (60, 0.00, 0.25, 0.0, True),
            (62, 0.25, 0.50, 1.0, False),
        )
    )
    original_events = tempo.original.events
    result = QuantizeMonophonicRhythm().execute(tempo, RhythmQuantizationSettings())
    notes = tuple(item for item in result.timeline if isinstance(item, QuantizedNoteEvent))

    assert tempo.original.events is original_events
    assert tuple(note.source_index for note in notes) == (1, 2, 0)
    assert tuple(note.source for note in notes) == (
        original_events[1],
        original_events[2],
        original_events[0],
    )
    assert all(
        left.quantized_offset_step <= right.quantized_onset_step for left, right in pairwise(notes)
    )


def test_confidence_low_confidence_and_both_pitches_remain_identical() -> None:
    tempo = manual_resolution(
        (
            (60, 0.0, 0.25, 0.0, True),
            (67, 0.25, 0.50, 1.0, False),
        )
    )
    result = QuantizeMonophonicRhythm().execute(tempo, RhythmQuantizationSettings())
    notes = tuple(item for item in result.timeline if isinstance(item, QuantizedNoteEvent))

    for note in notes:
        original = tempo.original.events[note.source_index]
        assert note.source is original
        assert note.source.source.event is original.source.event
        assert (
            note.source.source.event.pitch_concert_midi == original.source.event.pitch_concert_midi
        )
        assert note.source.written_pitch_midi == original.written_pitch_midi
        assert note.source.source.event.confidence == original.source.event.confidence
        assert note.source.source.is_low_confidence is original.source.is_low_confidence


def valid_single_result() -> QuantizedRhythmResult:
    return quantize(((60, 0.0, 0.25, 0.8, False),))


@pytest.mark.parametrize(
    "timeline",
    [
        (QuantizedRest(1, 2),),
        (QuantizedRest(0, 1), QuantizedRest(1, 2)),
        (QuantizedRest(0, 1),),
    ],
)
def test_result_rejects_timeline_without_exact_source_coverage(
    timeline: tuple[object, ...],
) -> None:
    base = valid_single_result()
    with pytest.raises(InvalidQuantizedRhythmResultError):
        QuantizedRhythmResult(
            tempo=base.tempo,
            timeline=cast(Any, timeline),
            report=base.report,
        )


def test_result_rejects_repeated_source_index_and_replaced_reference() -> None:
    base = quantize(
        (
            (60, 0.0, 0.25, 0.8, False),
            (62, 0.25, 0.50, 0.8, False),
        )
    )
    notes = tuple(item for item in base.timeline if isinstance(item, QuantizedNoteEvent))
    repeated = QuantizedNoteEvent(
        source=notes[1].source,
        source_index=0,
        quantized_onset_step=notes[1].quantized_onset_step,
        quantized_offset_step=notes[1].quantized_offset_step,
        onset_delta_seconds=notes[1].onset_delta_seconds,
        offset_delta_seconds=notes[1].offset_delta_seconds,
    )
    with pytest.raises(InvalidQuantizedRhythmResultError):
        QuantizedRhythmResult(
            tempo=base.tempo,
            timeline=(notes[0], repeated),
            report=base.report,
        )


def test_result_rejects_gap_without_rest_overlap_and_inconsistent_metrics() -> None:
    base = quantize(
        (
            (60, 0.0, 0.25, 0.8, False),
            (62, 0.50, 0.75, 0.8, False),
        )
    )
    notes = tuple(item for item in base.timeline if isinstance(item, QuantizedNoteEvent))
    with pytest.raises(InvalidQuantizedRhythmResultError):
        QuantizedRhythmResult(
            tempo=base.tempo,
            timeline=notes,
            report=base.report,
        )

    overlapping = QuantizedNoteEvent(
        source=notes[1].source,
        source_index=notes[1].source_index,
        quantized_onset_step=1,
        quantized_offset_step=3,
        onset_delta_seconds=notes[1].onset_delta_seconds,
        offset_delta_seconds=notes[1].offset_delta_seconds,
    )
    with pytest.raises(InvalidQuantizedRhythmResultError):
        QuantizedRhythmResult(
            tempo=base.tempo,
            timeline=(notes[0], overlapping),
            report=RhythmQuantizationReport(
                settings=base.report.settings,
                input_event_count=2,
                quantized_note_count=2,
                rest_count=0,
                minimum_duration_adjustment_count=0,
                overlap_adjusted_event_count=0,
                total_absolute_onset_delta_seconds=sum(
                    abs(note.onset_delta_seconds) for note in (notes[0], overlapping)
                ),
                total_absolute_offset_delta_seconds=sum(
                    abs(note.offset_delta_seconds) for note in (notes[0], overlapping)
                ),
                maximum_absolute_boundary_delta_seconds=max(
                    abs(delta)
                    for note in (notes[0], overlapping)
                    for delta in (note.onset_delta_seconds, note.offset_delta_seconds)
                ),
            ),
        )

    wrong_report = RhythmQuantizationReport(
        settings=base.report.settings,
        input_event_count=2,
        quantized_note_count=2,
        rest_count=1,
        minimum_duration_adjustment_count=0,
        overlap_adjusted_event_count=0,
        total_absolute_onset_delta_seconds=999.0,
        total_absolute_offset_delta_seconds=base.report.total_absolute_offset_delta_seconds,
        maximum_absolute_boundary_delta_seconds=999.0,
    )
    with pytest.raises(InvalidQuantizedRhythmResultError):
        QuantizedRhythmResult(
            tempo=base.tempo,
            timeline=base.timeline,
            report=wrong_report,
        )


def test_result_rejects_non_tempo_resolution() -> None:
    base = valid_single_result()
    with pytest.raises(InvalidQuantizedRhythmResultError):
        QuantizedRhythmResult(
            tempo=cast(Any, object()),
            timeline=base.timeline,
            report=base.report,
        )


def test_architecture_and_scope_boundaries() -> None:
    domain = (ROOT / "src/saxo_ai/domain/rhythm_quantization.py").read_text()
    application = (ROOT / "src/saxo_ai/application/rhythm_quantization.py").read_text()
    workflow = (ROOT / ".github/workflows/quality.yml").read_text()

    for forbidden in (
        "fastapi",
        "mido",
        "torch",
        "huggingface_hub",
        "librosa",
        "numpy",
        "subprocess",
        "tempfile",
        "musicxml",
    ):
        assert forbidden not in (domain + application).lower()
    for future in ("time_signature", "key_signature", "measure", "tuplet"):
        assert future not in (domain + application).lower()
    assert "Python 3.11" not in workflow
    assert '"3.11"' in workflow and '"3.12"' in workflow and '"3.13"' in workflow
