from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import pytest

from saxo_ai.domain.midi_export import InvalidMidiExportSettingsError, MidiExportSettings
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
    DEFAULT_CONSENSUS_TOLERANCE,
    DEFAULT_MAXIMUM_BPM,
    DEFAULT_MINIMUM_BPM,
    DEFAULT_MINIMUM_INTERVAL_COUNT,
    TEMPO_CONFIDENCE_METHOD,
    TEMPO_ESTIMATOR_NAME,
    TEMPO_ESTIMATOR_VERSION,
    TEMPO_POLICY_VERSION,
    AutomaticTempoEstimate,
    InvalidTempoEstimateError,
    InvalidTempoResolutionError,
    InvalidTempoSettingsError,
    TempoEstimationSettings,
    TempoResolution,
    TempoSelectionSource,
)
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent, WrittenPitchTranscriptionResult

ROOT = Path(__file__).resolve().parents[2]


def written_result(onsets: tuple[float, ...] = (0.0, 0.5, 1.0)) -> WrittenPitchTranscriptionResult:
    notes = tuple(
        NoteEvent(60 + index, onset, onset + 0.25, 100, 0.8) for index, onset in enumerate(onsets)
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


def automatic(confidence: float = 1.0) -> AutomaticTempoEstimate:
    return AutomaticTempoEstimate(
        120.0,
        confidence,
        TEMPO_ESTIMATOR_NAME,
        TEMPO_ESTIMATOR_VERSION,
        TEMPO_CONFIDENCE_METHOD,
        4,
        3,
        round(confidence * 3),
    )


def test_constants_defaults_and_string_enum_are_stable() -> None:
    settings = TempoEstimationSettings()

    assert (
        TEMPO_POLICY_VERSION,
        TEMPO_ESTIMATOR_NAME,
        TEMPO_ESTIMATOR_VERSION,
        TEMPO_CONFIDENCE_METHOD,
    ) == (
        "1.0",
        "median_onset_interval",
        "1.0",
        "octave_equivalent_ioi_consensus_ratio",
    )
    assert (
        (settings.minimum_bpm, settings.maximum_bpm)
        == (
            DEFAULT_MINIMUM_BPM,
            DEFAULT_MAXIMUM_BPM,
        )
        == (40.0, 240.0)
    )
    assert settings.minimum_interval_count == DEFAULT_MINIMUM_INTERVAL_COUNT == 2
    assert settings.consensus_tolerance == DEFAULT_CONSENSUS_TOLERANCE == 0.08
    assert TempoSelectionSource.AUTOMATIC.value == "automatic"
    assert TempoSelectionSource.MANUAL.value == "manual"
    assert str(TempoSelectionSource.MANUAL) == "manual"


@pytest.mark.parametrize(
    "changes",
    [
        {"minimum_bpm": value}
        for value in (True, False, "40", None, 0, -1, float("nan"), float("inf"))
    ]
    + [{"maximum_bpm": value} for value in (True, 0, float("-inf"))]
    + [
        {"minimum_bpm": 120, "maximum_bpm": 120},
        {"minimum_bpm": 121, "maximum_bpm": 120},
    ]
    + [{"minimum_interval_count": value} for value in (0, -1, True, 2.0)]
    + [{"consensus_tolerance": value} for value in (-0.01, 1.01, True, float("nan"))]
    + [{"policy_version": "2.0"}],
)
def test_invalid_settings_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "minimum_bpm": 40,
        "maximum_bpm": 240,
        "minimum_interval_count": 2,
        "consensus_tolerance": 0.08,
        "policy_version": "1.0",
    }
    values.update(changes)
    with pytest.raises(InvalidTempoSettingsError):
        TempoEstimationSettings(**cast(Any, values))


def test_estimate_normalizes_and_enforces_exact_confidence_formula() -> None:
    estimate = AutomaticTempoEstimate(
        120,
        0.75,
        TEMPO_ESTIMATOR_NAME,
        TEMPO_ESTIMATOR_VERSION,
        TEMPO_CONFIDENCE_METHOD,
        5,
        4,
        3,
    )

    assert estimate.tempo_bpm == 120.0
    assert estimate.confidence == estimate.inlier_interval_count / estimate.interval_count == 0.75


@pytest.mark.parametrize(
    "changes",
    [
        {"tempo_bpm": 0},
        {"tempo_bpm": True},
        {"tempo_bpm": float("nan")},
        {"confidence": -0.01},
        {"confidence": 1.01},
        {"confidence": True},
        {"estimator_name": ""},
        {"estimator_version": " "},
        {"confidence_method": ""},
        {"unique_onset_count": -1},
        {"unique_onset_count": True},
        {"interval_count": 2},
        {"inlier_interval_count": 4},
        {"confidence": 0.5},
    ],
)
def test_invalid_estimates_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "tempo_bpm": 120.0,
        "confidence": 1.0,
        "estimator_name": TEMPO_ESTIMATOR_NAME,
        "estimator_version": TEMPO_ESTIMATOR_VERSION,
        "confidence_method": TEMPO_CONFIDENCE_METHOD,
        "unique_onset_count": 4,
        "interval_count": 3,
        "inlier_interval_count": 3,
    }
    values.update(changes)
    with pytest.raises(InvalidTempoEstimateError):
        AutomaticTempoEstimate(**cast(Any, values))


def test_automatic_and_manual_resolution_invariants() -> None:
    original = written_result()
    estimate = automatic()
    auto = TempoResolution(original, estimate, None, 120, TempoSelectionSource.AUTOMATIC, 1)
    manual = TempoResolution(written_result(()), None, 90, 90, TempoSelectionSource.MANUAL, 1)

    assert auto.original is original
    assert auto.automatic_estimate is estimate
    assert auto.effective_tempo_bpm == 120.0
    assert manual.automatic_estimate is None
    assert manual.manual_tempo_bpm == manual.effective_tempo_bpm == 90.0


@pytest.mark.parametrize(
    "changes",
    [
        {"original": object()},
        {"source": "automatic"},
        {"revision": 0},
        {"revision": True},
        {"policy_version": "2.0"},
        {"automatic_estimate": None},
        {"manual_tempo_bpm": 90.0},
        {"effective_tempo_bpm": 121.0},
        {"revision": 2},
    ],
)
def test_invalid_automatic_resolutions_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "original": written_result(),
        "automatic_estimate": automatic(),
        "manual_tempo_bpm": None,
        "effective_tempo_bpm": 120,
        "source": TempoSelectionSource.AUTOMATIC,
        "revision": 1,
        "policy_version": "1.0",
    }
    values.update(changes)
    with pytest.raises(InvalidTempoResolutionError):
        TempoResolution(**cast(Any, values))


def test_contracts_are_immutable() -> None:
    settings = TempoEstimationSettings()
    estimate = automatic()
    resolution = TempoResolution(
        written_result(), estimate, None, 120, TempoSelectionSource.AUTOMATIC, 1
    )

    with pytest.raises(FrozenInstanceError):
        settings.minimum_bpm = 60.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        estimate.confidence = 0.5  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        resolution.revision = 2  # type: ignore[misc]


@pytest.mark.parametrize("value", [60, 120, 60_000_000 / 16_777_215])
def test_midi_settings_keep_existing_positive_bpm_behavior(value: float) -> None:
    assert MidiExportSettings(tempo_bpm=value).tempo_bpm == float(value)


@pytest.mark.parametrize("value", [True, 0, -1, 1.0, float("nan"), float("inf")])
def test_midi_settings_keep_rejecting_invalid_bpm(value: object) -> None:
    with pytest.raises(InvalidMidiExportSettingsError):
        MidiExportSettings(tempo_bpm=cast(Any, value))


def test_architecture_and_scope_boundaries() -> None:
    domain = (ROOT / "src/saxo_ai/domain/tempo.py").read_text()
    application = (ROOT / "src/saxo_ai/application/tempo_resolution.py").read_text()
    infrastructure = (ROOT / "src/saxo_ai/infrastructure/onset_interval_tempo.py").read_text()
    pyproject = (ROOT / "pyproject.toml").read_text()

    for forbidden in ("fastapi", "mido", "librosa", "numpy", "scipy", "musicxml"):
        assert forbidden not in domain.lower()
    assert "fastapi" not in application.lower()
    assert "mido" not in application.lower()
    assert "onset_seconds" in infrastructure
    assert "Quantized" not in domain + application + infrastructure
    for dependency in ("librosa", "aubio", "essentia", "madmom", "numpy", "scipy"):
        assert dependency not in pyproject
