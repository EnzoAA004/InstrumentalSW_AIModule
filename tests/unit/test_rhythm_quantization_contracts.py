from __future__ import annotations

from dataclasses import FrozenInstanceError
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

from saxo_ai.domain.rhythm_quantization import (
    DEFAULT_SUBDIVISIONS_PER_BEAT,
    OVERLAP_POLICY,
    QUANTIZATION_ROUNDING_MODE,
    REST_POLICY,
    RHYTHM_QUANTIZATION_POLICY_VERSION,
    InvalidQuantizedNoteError,
    InvalidQuantizedRestError,
    InvalidRhythmQuantizationReportError,
    InvalidRhythmQuantizationSettingsError,
    QuantizedNoteEvent,
    QuantizedRest,
    RhythmQuantizationReport,
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


def test_settings_defaults_and_policy_constants_are_stable() -> None:
    settings = RhythmQuantizationSettings()

    assert settings.subdivisions_per_beat == DEFAULT_SUBDIVISIONS_PER_BEAT == 4
    assert settings.policy_version == RHYTHM_QUANTIZATION_POLICY_VERSION == "1.0"
    assert QUANTIZATION_ROUNDING_MODE == "nearest_half_up"
    assert OVERLAP_POLICY == "truncate_earlier_then_shift_same_step"
    assert REST_POLICY == "explicit_positive_grid_gaps"


@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "4", None])
def test_settings_reject_invalid_subdivisions(value: object) -> None:
    with pytest.raises(InvalidRhythmQuantizationSettingsError):
        RhythmQuantizationSettings(subdivisions_per_beat=cast(Any, value))


def test_settings_reject_unknown_policy_version() -> None:
    with pytest.raises(InvalidRhythmQuantizationSettingsError):
        RhythmQuantizationSettings(policy_version="2.0")


def test_settings_are_frozen_and_slotted() -> None:
    settings = RhythmQuantizationSettings()
    assert not hasattr(settings, "__dict__")
    with pytest.raises(FrozenInstanceError):
        settings.subdivisions_per_beat = 8  # type: ignore[misc]


def test_quantized_note_preserves_source_and_signed_deltas() -> None:
    source = written_result(((60, 0.13, 0.49, 0.0, True),)).events[0]
    note = QuantizedNoteEvent(
        source=source,
        source_index=0,
        quantized_onset_step=1,
        quantized_offset_step=4,
        onset_delta_seconds=-0.005,
        offset_delta_seconds=0.01,
    )

    assert note.source is source
    assert note.duration_steps == 3
    assert note.onset_delta_seconds == -0.005
    assert note.offset_delta_seconds == 0.01
    assert not hasattr(note, "__dict__")
    with pytest.raises(FrozenInstanceError):
        note.quantized_offset_step = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"source": object()},
        {"source_index": -1},
        {"source_index": True},
        {"quantized_onset_step": -1},
        {"quantized_onset_step": True},
        {"quantized_offset_step": 1.5},
        {"quantized_offset_step": 1},
        {"quantized_offset_step": 0},
        {"onset_delta_seconds": float("nan")},
        {"offset_delta_seconds": float("inf")},
        {"onset_delta_seconds": True},
    ],
)
def test_invalid_quantized_notes_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "source": written_result(((60, 0.0, 0.5, 0.8, False),)).events[0],
        "source_index": 0,
        "quantized_onset_step": 1,
        "quantized_offset_step": 2,
        "onset_delta_seconds": 0.0,
        "offset_delta_seconds": 0.0,
    }
    values.update(changes)
    with pytest.raises(InvalidQuantizedNoteError):
        QuantizedNoteEvent(**cast(Any, values))


def test_quantized_rest_is_positive_frozen_interval() -> None:
    rest = QuantizedRest(2, 4)

    assert rest.duration_steps == 2
    assert not hasattr(rest, "__dict__")
    with pytest.raises(FrozenInstanceError):
        rest.offset_step = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    ("onset", "offset"),
    [(-1, 1), (0, 0), (2, 1), (True, 2), (0, False), (0.0, 1)],
)
def test_invalid_rests_are_rejected(onset: object, offset: object) -> None:
    with pytest.raises(InvalidQuantizedRestError):
        QuantizedRest(cast(Any, onset), cast(Any, offset))


def test_report_enforces_counts_and_finite_non_negative_metrics() -> None:
    settings = RhythmQuantizationSettings()
    report = RhythmQuantizationReport(
        settings=settings,
        input_event_count=2,
        quantized_note_count=2,
        rest_count=1,
        minimum_duration_adjustment_count=1,
        overlap_adjusted_event_count=1,
        total_absolute_onset_delta_seconds=0.1,
        total_absolute_offset_delta_seconds=0.2,
        maximum_absolute_boundary_delta_seconds=0.15,
    )

    assert report.settings is settings
    assert report.total_absolute_timing_delta_seconds == pytest.approx(0.3)
    assert report.mean_absolute_boundary_delta_seconds == pytest.approx(0.075)


@pytest.mark.parametrize(
    "changes",
    [
        {"settings": object()},
        {"input_event_count": -1},
        {"input_event_count": True},
        {"quantized_note_count": 1},
        {"rest_count": -1},
        {"minimum_duration_adjustment_count": 3},
        {"overlap_adjusted_event_count": 3},
        {"total_absolute_onset_delta_seconds": -0.1},
        {"total_absolute_offset_delta_seconds": float("nan")},
        {"maximum_absolute_boundary_delta_seconds": float("inf")},
    ],
)
def test_invalid_reports_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "settings": RhythmQuantizationSettings(),
        "input_event_count": 2,
        "quantized_note_count": 2,
        "rest_count": 0,
        "minimum_duration_adjustment_count": 0,
        "overlap_adjusted_event_count": 0,
        "total_absolute_onset_delta_seconds": 0.0,
        "total_absolute_offset_delta_seconds": 0.0,
        "maximum_absolute_boundary_delta_seconds": 0.0,
    }
    values.update(changes)
    with pytest.raises(InvalidRhythmQuantizationReportError):
        RhythmQuantizationReport(**cast(Any, values))
