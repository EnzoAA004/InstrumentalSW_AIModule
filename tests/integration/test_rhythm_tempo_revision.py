from __future__ import annotations

import pytest

from saxo_ai.application.rhythm_quantization import QuantizeMonophonicRhythm
from saxo_ai.application.tempo_resolution import ConfigureManualTempo, OverrideEstimatedTempo
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
from saxo_ai.domain.rhythm_quantization import QuantizedNoteEvent, RhythmQuantizationSettings
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


pytestmark = pytest.mark.integration


def test_quantization_regenerates_for_exact_tempo_revision_without_reusing_previous_result() -> (
    None
):
    first_resolution = manual_resolution(
        (
            (60, 0.125, 0.50, 0.0, True),
            (62, 0.625, 1.00, 1.0, False),
        ),
        bpm=120.0,
    )
    use_case = QuantizeMonophonicRhythm()
    settings = RhythmQuantizationSettings()
    first = use_case.execute(first_resolution, settings)

    overridden_resolution = OverrideEstimatedTempo().execute(first_resolution, 60.0)
    second = use_case.execute(overridden_resolution, settings)

    first_notes = tuple(item for item in first.timeline if isinstance(item, QuantizedNoteEvent))
    second_notes = tuple(item for item in second.timeline if isinstance(item, QuantizedNoteEvent))

    assert first.tempo is first_resolution
    assert second.tempo is overridden_resolution
    assert first.tempo.revision == 1
    assert second.tempo.revision == 2
    assert first.tempo.effective_tempo_bpm == 120.0
    assert second.tempo.effective_tempo_bpm == 60.0
    assert first.timeline != second.timeline
    assert (
        first_notes[0].quantized_onset_step,
        first_notes[0].quantized_offset_step,
    ) != (
        second_notes[0].quantized_onset_step,
        second_notes[0].quantized_offset_step,
    )
    assert tuple(note.source for note in first_notes) == tuple(note.source for note in second_notes)
    assert all(
        first_note.source is second_note.source
        for first_note, second_note in zip(first_notes, second_notes, strict=True)
    )
    assert first.tempo is first_resolution
    assert first.report.settings is settings
