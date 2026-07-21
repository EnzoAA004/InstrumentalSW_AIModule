from __future__ import annotations

from saxo_ai.application.rhythm_quantization import QuantizeMonophonicRhythm
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
from saxo_ai.domain.rhythm_quantization import QuantizedRhythmResult, RhythmQuantizationSettings
from saxo_ai.domain.tempo import (
    TEMPO_CONFIDENCE_METHOD,
    TEMPO_ESTIMATOR_NAME,
    TEMPO_ESTIMATOR_VERSION,
    AutomaticTempoEstimate,
    TempoResolution,
    TempoSelectionSource,
)
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.transposition import transpose_concert_pitch
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent, WrittenPitchTranscriptionResult

NoteSpec = tuple[int, float, float, float, bool]


def written_result(
    specs: tuple[NoteSpec, ...],
    *,
    saxophone_type: SaxophoneType = SaxophoneType.ALTO,
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
            NoteEventPostProcessingSettings(), len(notes), len(notes), 0, 0, 0
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
            LowConfidenceSettings(), len(notes), low_count, len(notes) - low_count
        ),
    )
    return WrittenPitchTranscriptionResult(
        annotated,
        saxophone_type,
        tuple(
            WrittenPitchNoteEvent(
                annotation,
                transpose_concert_pitch(annotation.event.pitch_concert_midi, saxophone_type),
            )
            for annotation in annotations
        ),
    )


def manual_quantized(
    specs: tuple[NoteSpec, ...],
    *,
    saxophone_type: SaxophoneType = SaxophoneType.ALTO,
    bpm: float = 120.0,
    subdivisions: int = 4,
    revision: int = 1,
) -> QuantizedRhythmResult:
    original = written_result(specs, saxophone_type=saxophone_type)
    tempo = TempoResolution(
        original=original,
        automatic_estimate=None,
        manual_tempo_bpm=bpm,
        effective_tempo_bpm=bpm,
        source=TempoSelectionSource.MANUAL,
        revision=revision,
    )
    return QuantizeMonophonicRhythm().execute(
        tempo,
        RhythmQuantizationSettings(subdivisions),
    )


def automatic_quantized(
    specs: tuple[NoteSpec, ...],
    *,
    saxophone_type: SaxophoneType = SaxophoneType.ALTO,
    bpm: float = 120.0,
    subdivisions: int = 4,
) -> QuantizedRhythmResult:
    original = written_result(specs, saxophone_type=saxophone_type)
    estimate = AutomaticTempoEstimate(
        tempo_bpm=bpm,
        confidence=1.0,
        estimator_name=TEMPO_ESTIMATOR_NAME,
        estimator_version=TEMPO_ESTIMATOR_VERSION,
        confidence_method=TEMPO_CONFIDENCE_METHOD,
        unique_onset_count=3,
        interval_count=2,
        inlier_interval_count=2,
    )
    tempo = TempoResolution(
        original=original,
        automatic_estimate=estimate,
        manual_tempo_bpm=None,
        effective_tempo_bpm=bpm,
        source=TempoSelectionSource.AUTOMATIC,
        revision=1,
    )
    return QuantizeMonophonicRhythm().execute(
        tempo,
        RhythmQuantizationSettings(subdivisions),
    )
