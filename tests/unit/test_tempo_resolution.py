from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from saxo_ai.application.midi_export import ExportWrittenPitchToMidi
from saxo_ai.application.tempo_resolution import (
    ConfigureManualTempo,
    ExportTempoResolvedMidi,
    OverrideEstimatedTempo,
    TempoResolvedMidiResult,
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
from saxo_ai.domain.tempo import (
    TEMPO_CONFIDENCE_METHOD,
    TEMPO_ESTIMATOR_NAME,
    TEMPO_ESTIMATOR_VERSION,
    AutomaticTempoEstimate,
    InvalidTempoResolutionError,
    InvalidTempoSettingsError,
    TempoResolution,
    TempoSelectionSource,
)
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.written_pitch import (
    WrittenPitchNoteEvent,
    WrittenPitchTranscriptionResult,
)


def written_result(onsets: tuple[float, ...]) -> WrittenPitchTranscriptionResult:
    notes = tuple(NoteEvent(60 + index, onset, onset + 0.5, 100, 0.8) for index, onset in enumerate(onsets))
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
        NoteEventPostProcessingReport(
            NoteEventPostProcessingSettings(), len(notes), len(notes), 0, 0, 0
        ),
    )
    annotations = tuple(
        ConfidenceAnnotatedNoteEvent(note, index == 0) for index, note in enumerate(notes)
    )
    annotated = ConfidenceAnnotatedTranscriptionResult(
        processed,
        annotations,
        LowConfidenceReport(
            LowConfidenceSettings(), len(notes), int(bool(notes)), len(notes) - int(bool(notes))
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


def automatic_resolution(original: WrittenPitchTranscriptionResult) -> TempoResolution:
    estimate = AutomaticTempoEstimate(
        120.0,
        1.0,
        TEMPO_ESTIMATOR_NAME,
        TEMPO_ESTIMATOR_VERSION,
        TEMPO_CONFIDENCE_METHOD,
        3,
        2,
        2,
    )
    return TempoResolution(
        original,
        estimate,
        None,
        120.0,
        TempoSelectionSource.AUTOMATIC,
        1,
    )


class RecordingMidiEncoder:
    def encode(self, *, plan: tuple[Any, ...], settings: Any) -> bytes:
        return b"MThd" + repr((settings.tempo_bpm, plan)).encode()


@pytest.mark.parametrize("onsets", [(), (0.0,), (0.0, 0.5)])
def test_manual_configuration_works_without_automatic_estimate(
    onsets: tuple[float, ...]
) -> None:
    original = written_result(onsets)

    resolution = ConfigureManualTempo().execute(original, 90)

    assert resolution.original is original
    assert resolution.automatic_estimate is None
    assert resolution.manual_tempo_bpm == resolution.effective_tempo_bpm == 90.0
    assert resolution.source is TempoSelectionSource.MANUAL
    assert resolution.revision == 1


@pytest.mark.parametrize(
    "tempo", [True, False, "120", None, 0, -1, float("nan"), float("inf")]
)
def test_manual_configuration_rejects_invalid_bpm(tempo: object) -> None:
    with pytest.raises(InvalidTempoSettingsError):
        ConfigureManualTempo().execute(written_result(()), cast(Any, tempo))


def test_manual_configuration_preserves_complete_provenance() -> None:
    original = written_result((0.0, 0.5, 1.0))

    resolution = ConfigureManualTempo().execute(original, 100)

    assert resolution.original is original
    assert resolution.original.original is original.original
    assert resolution.original.events[0] is original.events[0]
    assert resolution.original.events[0].source.event.confidence == 0.8
    assert resolution.original.events[0].source.is_low_confidence is True
    assert resolution.original.original.original.original.model.checkpoint_filename == "filosax_25k.pth"


def test_override_preserves_automatic_estimate_original_and_history() -> None:
    previous = automatic_resolution(written_result((0.0, 0.5, 1.0)))

    overridden = OverrideEstimatedTempo().execute(previous, 90)

    assert overridden is not previous
    assert overridden.original is previous.original
    assert overridden.automatic_estimate is previous.automatic_estimate
    assert overridden.manual_tempo_bpm == overridden.effective_tempo_bpm == 90.0
    assert overridden.source is TempoSelectionSource.MANUAL
    assert overridden.revision == previous.revision + 1 == 2
    assert previous.source is TempoSelectionSource.AUTOMATIC
    assert previous.manual_tempo_bpm is None
    assert previous.revision == 1


def test_every_explicit_override_creates_a_new_revision_even_for_same_bpm() -> None:
    first = automatic_resolution(written_result((0.0, 0.5, 1.0)))
    second = OverrideEstimatedTempo().execute(first, 120)
    third = OverrideEstimatedTempo().execute(second, 120)

    assert second.revision == 2
    assert third.revision == 3
    assert second.automatic_estimate is first.automatic_estimate
    assert third.automatic_estimate is first.automatic_estimate


def test_override_rejects_invalid_previous_and_manual_bpm() -> None:
    with pytest.raises(InvalidTempoResolutionError):
        OverrideEstimatedTempo().execute(cast(Any, object()), 90)
    with pytest.raises(InvalidTempoSettingsError):
        OverrideEstimatedTempo().execute(
            automatic_resolution(written_result((0.0, 0.5, 1.0))), cast(Any, True)
        )


def test_tempo_resolved_midi_result_preserves_resolution_reference() -> None:
    resolution = ConfigureManualTempo().execute(written_result((0.0, 0.5)), 90)
    exporter = ExportTempoResolvedMidi(
        ExportWrittenPitchToMidi(cast(Any, RecordingMidiEncoder()))
    )

    result = exporter.execute(resolution)

    assert isinstance(result, TempoResolvedMidiResult)
    assert result.tempo is resolution
    assert result.midi.original is resolution.original
    assert result.midi.report.settings.tempo_bpm == resolution.effective_tempo_bpm == 90.0

    with pytest.raises(FrozenInstanceError):
        result.tempo = resolution  # type: ignore[misc]


def test_export_rejects_invalid_resolution_before_midi_export() -> None:
    exporter = ExportTempoResolvedMidi(
        ExportWrittenPitchToMidi(cast(Any, RecordingMidiEncoder()))
    )

    with pytest.raises(InvalidTempoResolutionError):
        exporter.execute(cast(Any, object()))
