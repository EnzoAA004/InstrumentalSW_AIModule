from typing import Any, cast

import pytest

from saxo_ai.application.tempo_resolution import (
    EstimateTranscriptionTempo,
    TempoEstimator,
    TempoEstimatorError,
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
    InvalidTempoEstimateError,
    InvalidTempoSettingsError,
    TempoEstimationSettings,
    TempoEstimationUnavailableError,
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
from saxo_ai.infrastructure.onset_interval_tempo import OnsetIntervalTempoEstimator


def written_result(onsets: tuple[float, ...]) -> WrittenPitchTranscriptionResult:
    notes = tuple(
        NoteEvent(60 + index, onset, onset + 0.1, 100, 0.8) for index, onset in enumerate(onsets)
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
        NoteEventPostProcessingReport(
            NoteEventPostProcessingSettings(), len(notes), len(notes), 0, 0, 0
        ),
    )
    annotations = tuple(ConfidenceAnnotatedNoteEvent(note, False) for note in notes)
    annotated = ConfidenceAnnotatedTranscriptionResult(
        processed,
        annotations,
        LowConfidenceReport(LowConfidenceSettings(), len(notes), 0, len(notes)),
    )
    return WrittenPitchTranscriptionResult(
        annotated,
        SaxophoneType.ALTO,
        tuple(
            WrittenPitchNoteEvent(annotation, annotation.event.pitch_concert_midi + 9)
            for annotation in annotations
        ),
    )


class RecordingEstimator:
    def __init__(self, result: AutomaticTempoEstimate) -> None:
        self.result = result
        self.calls: list[tuple[WrittenPitchTranscriptionResult, TempoEstimationSettings]] = []

    def estimate(
        self,
        original: WrittenPitchTranscriptionResult,
        settings: TempoEstimationSettings,
    ) -> AutomaticTempoEstimate:
        self.calls.append((original, settings))
        return self.result


class RaisingEstimator:
    def estimate(
        self,
        original: WrittenPitchTranscriptionResult,
        settings: TempoEstimationSettings,
    ) -> AutomaticTempoEstimate:
        raise RuntimeError("model path and private material must not leak")


class InvalidEstimator:
    def estimate(
        self,
        original: WrittenPitchTranscriptionResult,
        settings: TempoEstimationSettings,
    ) -> AutomaticTempoEstimate:
        return cast(AutomaticTempoEstimate, object())


def test_estimator_protocol_is_structural() -> None:
    estimate = AutomaticTempoEstimate(
        120.0,
        1.0,
        TEMPO_ESTIMATOR_NAME,
        TEMPO_ESTIMATOR_VERSION,
        TEMPO_CONFIDENCE_METHOD,
        4,
        3,
        3,
    )
    assert isinstance(RecordingEstimator(estimate), TempoEstimator)


@pytest.mark.parametrize(
    ("onsets", "expected_bpm"),
    [
        ((0.0, 0.5, 1.0, 1.5), 120.0),
        ((0.0, 1.0, 2.0, 3.0), 60.0),
    ],
)
def test_regular_onset_intervals_produce_expected_tempo(
    onsets: tuple[float, ...], expected_bpm: float
) -> None:
    original = written_result(onsets)

    result = OnsetIntervalTempoEstimator().estimate(original, TempoEstimationSettings())

    assert result.tempo_bpm == expected_bpm
    assert result.unique_onset_count == 4
    assert result.interval_count == 3
    assert result.inlier_interval_count == 3
    assert result.confidence == 1.0


def test_octave_equivalent_subdivisions_reach_deterministic_consensus() -> None:
    original = written_result((0.0, 1.0, 1.5, 1.75))

    result = OnsetIntervalTempoEstimator().estimate(original, TempoEstimationSettings())

    assert result.tempo_bpm == 120.0
    assert result.interval_count == 3
    assert result.inlier_interval_count == 3
    assert result.confidence == 1.0


def test_clear_timing_outlier_reduces_consensus_confidence() -> None:
    original = written_result((0.0, 0.5, 1.0, 2.0, 2.2))

    result = OnsetIntervalTempoEstimator().estimate(original, TempoEstimationSettings())

    assert result.tempo_bpm == 120.0
    assert result.interval_count == 4
    assert result.inlier_interval_count == 3
    assert result.confidence == result.inlier_interval_count / result.interval_count == 0.75


def test_exact_duplicate_onsets_are_deduplicated_only_for_estimation() -> None:
    original = written_result((1.0, 0.0, 0.5, 0.5, 1.5))
    original_events = original.events
    original_onsets = tuple(item.source.event.onset_seconds for item in original.events)

    result = OnsetIntervalTempoEstimator().estimate(original, TempoEstimationSettings())

    assert result.tempo_bpm == 120.0
    assert result.unique_onset_count == 4
    assert result.interval_count == 3
    assert original.events is original_events
    assert tuple(item.source.event.onset_seconds for item in original.events) == original_onsets


@pytest.mark.parametrize("onsets", [(), (0.0,), (0.0, 0.5)])
def test_insufficient_material_raises_controlled_counts(onsets: tuple[float, ...]) -> None:
    settings = TempoEstimationSettings(minimum_interval_count=2)

    with pytest.raises(TempoEstimationUnavailableError) as captured:
        OnsetIntervalTempoEstimator().estimate(written_result(onsets), settings)

    assert captured.value.unique_onset_count == len(set(onsets))
    assert captured.value.interval_count == max(0, len(set(onsets)) - 1)
    assert captured.value.minimum_interval_count == 2
    assert "filosax" not in str(captured.value).lower()
    assert "checkpoint" not in str(captured.value).lower()


def test_no_octave_equivalent_inside_range_fails_without_clipping() -> None:
    settings = TempoEstimationSettings(minimum_bpm=100, maximum_bpm=110)

    with pytest.raises(TempoEstimationUnavailableError):
        OnsetIntervalTempoEstimator().estimate(written_result((0.0, 1.0, 2.0)), settings)


def test_estimation_use_case_calls_port_once_and_selects_revision_one() -> None:
    original = written_result((0.0, 0.5, 1.0, 1.5))
    settings = TempoEstimationSettings()
    automatic = AutomaticTempoEstimate(
        120.0,
        1.0,
        TEMPO_ESTIMATOR_NAME,
        TEMPO_ESTIMATOR_VERSION,
        TEMPO_CONFIDENCE_METHOD,
        4,
        3,
        3,
    )
    estimator = RecordingEstimator(automatic)

    resolution = EstimateTranscriptionTempo(estimator).execute(original, settings)

    assert estimator.calls == [(original, settings)]
    assert resolution.original is original
    assert resolution.automatic_estimate is automatic
    assert resolution.effective_tempo_bpm == 120.0
    assert resolution.source is TempoSelectionSource.AUTOMATIC
    assert resolution.revision == 1


def test_estimation_use_case_rejects_invalid_input_before_port() -> None:
    automatic = AutomaticTempoEstimate(
        120.0,
        1.0,
        TEMPO_ESTIMATOR_NAME,
        TEMPO_ESTIMATOR_VERSION,
        TEMPO_CONFIDENCE_METHOD,
        4,
        3,
        3,
    )
    estimator = RecordingEstimator(automatic)

    with pytest.raises(InvalidTempoEstimateError):
        EstimateTranscriptionTempo(estimator).execute(
            cast(Any, object()), TempoEstimationSettings()
        )
    with pytest.raises(InvalidTempoSettingsError):
        EstimateTranscriptionTempo(estimator).execute(
            written_result((0.0, 0.5, 1.0)), cast(Any, object())
        )
    assert estimator.calls == []


def test_unexpected_estimator_failure_is_wrapped_without_sensitive_message() -> None:
    with pytest.raises(TempoEstimatorError) as captured:
        EstimateTranscriptionTempo(RaisingEstimator()).execute(
            written_result((0.0, 0.5, 1.0)), TempoEstimationSettings()
        )

    assert isinstance(captured.value.__cause__, RuntimeError)
    assert "private material" not in str(captured.value)
    assert "path" not in str(captured.value).lower()


def test_invalid_estimator_return_is_controlled() -> None:
    with pytest.raises(InvalidTempoEstimateError):
        EstimateTranscriptionTempo(InvalidEstimator()).execute(
            written_result((0.0, 0.5, 1.0)), TempoEstimationSettings()
        )


def test_estimator_rejects_invalid_contract_arguments() -> None:
    estimator = OnsetIntervalTempoEstimator()

    with pytest.raises(InvalidTempoEstimateError):
        estimator.estimate(cast(Any, object()), TempoEstimationSettings())
    with pytest.raises(InvalidTempoSettingsError):
        estimator.estimate(written_result((0.0, 0.5, 1.0)), cast(Any, object()))
