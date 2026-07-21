from __future__ import annotations

import io
from typing import Any

import mido  # type: ignore[import-untyped]
import pytest

from saxo_ai.application.midi_export import ExportWrittenPitchToMidi
from saxo_ai.application.tempo_resolution import (
    EstimateTranscriptionTempo,
    ExportTempoResolvedMidi,
    OverrideEstimatedTempo,
)
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
from saxo_ai.domain.tempo import TempoEstimationSettings, TempoSelectionSource
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.written_pitch import (
    WrittenPitchNoteEvent,
    WrittenPitchTranscriptionResult,
)
from saxo_ai.infrastructure.mido_midi import MidoMidiFileEncoder
from saxo_ai.infrastructure.onset_interval_tempo import OnsetIntervalTempoEstimator

pytestmark = [pytest.mark.integration, pytest.mark.midi_integration]


def written_result() -> WrittenPitchTranscriptionResult:
    notes = (
        NoteEvent(60, 0.0, 0.5, 100, 0.4),
        NoteEvent(62, 0.5, 1.0, 0, 0.8),
        NoteEvent(64, 1.0, 1.5, 127, 1.0),
    )
    batch = NoteEventBatch(notes)
    raw = TranscriptionResult(
        batch,
        TranscriptionModelIdentity(
            "filosax", "0.1.1", "a" * 40, "model", "b" * 40, "filosax_25k.pth", "c" * 64
        ),
        TranscriptionSettings(16_000, "cpu", 0.3, 0.3, 0.1, "activation"),
    )
    processed = PostProcessedTranscriptionResult(
        raw,
        batch,
        NoteEventPostProcessingReport(NoteEventPostProcessingSettings(), 3, 3, 0, 0, 0),
    )
    annotations = (
        ConfidenceAnnotatedNoteEvent(notes[0], True),
        ConfidenceAnnotatedNoteEvent(notes[1], False),
        ConfidenceAnnotatedNoteEvent(notes[2], False),
    )
    annotated = ConfidenceAnnotatedTranscriptionResult(
        processed,
        annotations,
        LowConfidenceReport(LowConfidenceSettings(), 3, 1, 2),
    )
    return WrittenPitchTranscriptionResult(
        annotated,
        SaxophoneType.ALTO,
        tuple(
            WrittenPitchNoteEvent(annotation, annotation.event.pitch_concert_midi + 9)
            for annotation in annotations
        ),
    )


def parse(content: bytes) -> Any:
    return mido.MidiFile(file=io.BytesIO(content))


def tempo_values(content: bytes) -> list[int]:
    return [message.tempo for message in parse(content).tracks[0] if message.type == "set_tempo"]


def absolute_note_ticks(content: bytes) -> list[tuple[int, str, int]]:
    absolute = 0
    result: list[tuple[int, str, int]] = []
    for message in parse(content).tracks[1]:
        absolute += message.time
        if message.type in {"note_on", "note_off"}:
            result.append((absolute, message.type, message.note))
    return result


def test_override_regenerates_midi_and_preserves_prior_result_and_provenance() -> None:
    original = written_result()
    automatic = EstimateTranscriptionTempo(OnsetIntervalTempoEstimator()).execute(
        original, TempoEstimationSettings()
    )
    exporter = ExportTempoResolvedMidi(ExportWrittenPitchToMidi(MidoMidiFileEncoder()))

    first = exporter.execute(automatic)
    overridden = OverrideEstimatedTempo().execute(automatic, 60)
    second = exporter.execute(overridden)

    assert automatic.source is TempoSelectionSource.AUTOMATIC
    assert automatic.effective_tempo_bpm == 120.0
    assert automatic.revision == 1
    assert overridden.source is TempoSelectionSource.MANUAL
    assert overridden.effective_tempo_bpm == 60.0
    assert overridden.revision == 2
    assert overridden.original is automatic.original is original
    assert overridden.automatic_estimate is automatic.automatic_estimate

    assert first.tempo is automatic
    assert second.tempo is overridden
    assert first.tempo.revision == 1
    assert second.tempo.revision == 2
    assert tempo_values(first.midi.artifact.content) == [500_000]
    assert tempo_values(second.midi.artifact.content) == [1_000_000]
    assert absolute_note_ticks(first.midi.artifact.content) != absolute_note_ticks(
        second.midi.artifact.content
    )
    assert first.midi.artifact.content != second.midi.artifact.content
    assert first.midi.artifact.sha256 != second.midi.artifact.sha256

    assert first.midi.original is second.midi.original is original
    assert [item.pitch_concert_midi for item in first.midi.plan] == [60, 62, 64]
    assert [item.source.written_pitch_midi for item in first.midi.plan] == [69, 71, 73]
    assert [item.source.source.is_low_confidence for item in first.midi.plan] == [True, False, False]
    assert original.original.original.original.model.checkpoint_filename == "filosax_25k.pth"
    assert original.original.original.original.settings.confidence_method == "activation"
    assert [item.source.event.onset_seconds for item in original.events] == [0.0, 0.5, 1.0]


def test_automatic_resolution_exports_its_estimated_tempo() -> None:
    automatic = EstimateTranscriptionTempo(OnsetIntervalTempoEstimator()).execute(
        written_result(), TempoEstimationSettings()
    )

    result = ExportTempoResolvedMidi(
        ExportWrittenPitchToMidi(MidoMidiFileEncoder())
    ).execute(automatic)

    assert result.tempo is automatic
    assert result.midi.report.settings.tempo_bpm == automatic.effective_tempo_bpm
    assert tempo_values(result.midi.artifact.content) == [500_000]
