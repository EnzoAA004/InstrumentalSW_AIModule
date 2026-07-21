from __future__ import annotations

import math
from typing import Any, cast

import pytest

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
from saxo_ai.domain.tempo import TempoResolution
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent, WrittenPitchTranscriptionResult

from saxo_ai.application.rhythm_quantization import (
    QuantizeMonophonicRhythm,
    grid_step_to_seconds,
    round_grid_position_half_up,
    seconds_per_grid_step,
    seconds_to_grid_step,
)
from saxo_ai.domain.rhythm_quantization import (
    QuantizedNoteEvent,
    RhythmQuantizationSettings,
)


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
        ConfidenceAnnotatedNoteEvent(note, specs[index][4])
        for index, note in enumerate(notes)
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


def notes_from(result: object) -> tuple[QuantizedNoteEvent, ...]:
    timeline = cast(Any, result).timeline
    return tuple(item for item in timeline if isinstance(item, QuantizedNoteEvent))


def quantize(
    specs: tuple[tuple[int, float, float, float, bool], ...],
    *,
    bpm: float = 120.0,
    subdivisions: int = 4,
):
    return QuantizeMonophonicRhythm().execute(
        manual_resolution(specs, bpm=bpm),
        RhythmQuantizationSettings(subdivisions),
    )


@pytest.mark.parametrize(
    ("position", "expected"),
    [(0.49, 0), (0.50, 1), (1.49, 1), (1.50, 2)],
)
def test_rounding_is_nearest_half_up(position: float, expected: int) -> None:
    assert round_grid_position_half_up(position) == expected


def test_grid_conversion_is_centralized_and_exact_at_known_boundary() -> None:
    assert seconds_per_grid_step(120.0, 4) == 0.125
    assert seconds_to_grid_step(0.125, 120.0, 4) == 1
    assert seconds_to_grid_step(0.500, 120.0, 4) == 4
    assert grid_step_to_seconds(4, 120.0, 4) == 0.5


@pytest.mark.parametrize("subdivisions", [2, 3, 4, 8])
def test_configurable_grid_produces_coherent_steps(subdivisions: int) -> None:
    result = quantize(
        ((60, 0.5, 1.0, 0.8, False),),
        bpm=60.0,
        subdivisions=subdivisions,
    )
    note = notes_from(result)[0]

    expected_onset = int(0.5 * subdivisions + 0.5)
    assert note.quantized_onset_step == expected_onset
    assert note.quantized_offset_step == subdivisions


def test_exact_120_bpm_four_subdivision_case() -> None:
    note = notes_from(quantize(((60, 0.125, 0.500, 0.8, False),)))[0]

    assert (note.quantized_onset_step, note.quantized_offset_step) == (1, 4)


def test_minimum_duration_is_one_step_and_reported() -> None:
    result = quantize(((60, 0.01, 0.02, 0.8, False),))
    note = notes_from(result)[0]

    assert note.duration_steps == 1
    assert result.report.minimum_duration_adjustment_count == 1


def test_later_attack_truncates_previous_note() -> None:
    result = quantize(
        (
            (60, 0.0, 0.50, 0.8, False),
            (62, 0.375, 0.75, 0.8, False),
        )
    )
    first, second = notes_from(result)

    assert (first.quantized_onset_step, first.quantized_offset_step) == (0, 3)
    assert (second.quantized_onset_step, second.quantized_offset_step) == (3, 6)
    assert result.report.overlap_adjusted_event_count == 1


@pytest.mark.parametrize("second_pitch", [60, 67])
def test_same_step_collision_shifts_current_without_pitch_priority(second_pitch: int) -> None:
    result = quantize(
        (
            (60, 0.0, 0.25, 0.8, False),
            (second_pitch, 0.01, 0.375, 0.8, False),
        )
    )
    first, second = notes_from(result)

    assert (first.quantized_onset_step, first.quantized_offset_step) == (0, 2)
    assert second.quantized_onset_step == first.quantized_offset_step
    assert second.quantized_offset_step > second.quantized_onset_step
    assert result.report.overlap_adjusted_event_count == 1


def test_overlap_chain_leaves_no_residual_overlap() -> None:
    result = quantize(
        (
            (60, 0.0, 0.75, 0.8, False),
            (62, 0.25, 0.875, 0.8, False),
            (64, 0.50, 1.00, 0.8, False),
            (65, 0.50, 1.125, 0.8, False),
        )
    )
    notes = notes_from(result)

    assert all(
        left.quantized_offset_step <= right.quantized_onset_step
        for left, right in zip(notes, notes[1:])
    )
    assert all(note.duration_steps >= 1 for note in notes)


def test_deltas_keep_sign_exact_boundaries_and_overlap_correction() -> None:
    result = quantize(
        (
            (60, 0.13, 0.49, 0.8, False),
            (62, 0.37, 0.76, 0.8, False),
        )
    )
    first, second = notes_from(result)

    assert math.isclose(first.onset_delta_seconds, 0.125 - 0.13, abs_tol=1e-12)
    assert math.isclose(first.offset_delta_seconds, 0.375 - 0.49, abs_tol=1e-12)
    assert first.onset_delta_seconds < 0.0
    assert first.offset_delta_seconds < 0.0
    assert math.isclose(second.onset_delta_seconds, 0.375 - 0.37, abs_tol=1e-12)
    assert second.onset_delta_seconds > 0.0


def test_report_metrics_are_calculated_from_final_note_deltas() -> None:
    result = quantize(
        (
            (60, 0.13, 0.49, 0.8, False),
            (62, 0.63, 0.99, 0.8, False),
        )
    )
    notes = notes_from(result)
    expected_onset = sum(abs(note.onset_delta_seconds) for note in notes)
    expected_offset = sum(abs(note.offset_delta_seconds) for note in notes)
    expected_maximum = max(
        abs(delta)
        for note in notes
        for delta in (note.onset_delta_seconds, note.offset_delta_seconds)
    )

    assert math.isclose(
        result.report.total_absolute_onset_delta_seconds,
        expected_onset,
        abs_tol=1e-12,
    )
    assert math.isclose(
        result.report.total_absolute_offset_delta_seconds,
        expected_offset,
        abs_tol=1e-12,
    )
    assert math.isclose(
        result.report.maximum_absolute_boundary_delta_seconds,
        expected_maximum,
        abs_tol=1e-12,
    )
