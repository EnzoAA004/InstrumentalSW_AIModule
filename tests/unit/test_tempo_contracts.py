from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import pytest

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
from saxo_ai.domain.written_pitch import (
    WrittenPitchNoteEvent,
    WrittenPitchTranscriptionResult,
)

ROOT = Path(__file__).resolve().parents[2]


def written_result(onsets: tuple[float, ...] = (0.0, 0.5, 1.0)) -> WrittenPitchTranscriptionResult:
    notes = tuple(NoteEvent(60 + index, onset, onset + 0.25, 100, 0.8) for index, onset in enumerate(onsets))
    batch = NoteEventBatch(notes)
    raw = TranscriptionResult(
        notes=batch,
        model=TranscriptionModelIdentity(
            "filosax", "0.1.1", "a" * 40, "model", "b" * 40, "filosax_25k.pth", "c" * 64
        ),
        settings=TranscriptionSettings(16_000, "cpu", 0.3, 0.3, 0.1, "activation"),
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


def estimate(*, bpm: float = 120.0, confidence: float = 1.0) -> AutomaticTempoEstimate:
    return AutomaticTempoEstimate(
        tempo_bpm=bpm,
        confidence=confidence,
        estimator_name=TEMPO_ESTIMATOR_NAME,
        estimator_version=TEMPO_ESTIMATOR_VERSION,
        confidence_method=TEMPO_CONFIDENCE_METHOD,
        unique_onset_count=4,
        interval_count=3,
        inlier_interval_count=round(confidence * 3),
    )


def test_tempo_constants_are_stable() -> None:
    assert TEMPO_POLICY_VERSION == "1.0"
    assert TEMPO_ESTIMATOR_NAME == "median_onset_interval"
    assert TEMPO_ESTIMATOR_VERSION == "1.0"
    assert DEFAULT_MINIMUM_BPM == 40.0
    assert DEFAULT_MAXIMUM_BPM == 240.0
    assert DEFAULT_MINIMUM_INTERVAL_COUNT == 2
    assert DEFAULT_CONSENSUS_TOLERANCE == 0.08
    assert TEMPO_CONFIDENCE_METHOD == "octave_equivalent_ioi_consensus_ratio"


def test_default_tempo_settings_are_normalized_and_immutable() -> None:
    settings = TempoEstimationSettings()

    assert settings.minimum_bpm == 40.0
    assert settings.maximum_bpm == 240.0
    assert settings.minimum_interval_count == 2
    assert settings.consensus_tolerance == 0.08
    assert settings.policy_version == "1.0"

    with pytest.raises(FrozenInstanceError):
        settings.minimum_bpm = 60.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"minimum_bpm": True},
        {"minimum_bpm": False},
        {"minimum_bpm": "40"},
        {"minimum_bpm": None},
        {"minimum_bpm": 0},
        {"minimum_bpm": -1},
        {"minimum_bpm": float("nan")},
        {"minimum_bpm": float("inf")},
        {"maximum_bpm": True},
        {"maximum_bpm": 0},
        {"maximum_bpm": float("-inf")},
        {"minimum_bpm": 120, "maximum_bpm": 120},
        {"minimum_bpm": 121, "maximum_bpm": 120},
        {"minimum_interval_count": 0},
        {"minimum_interval_count": -1},
        {"minimum_interval_count": True},
        {"minimum_interval_count": 2.0},
        {"consensus_tolerance": -0.01},
        {"consensus_tolerance": 1.01},
        {"consensus_tolerance": True},
        {"consensus_tolerance": float("nan")},
        {"policy_version": "2.0"},
    ],
)
def test_invalid_tempo_settings_are_rejected(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "minimum_bpm": 40.0,
        "maximum_bpm": 240.0,
        "minimum_interval_count": 2,
        "consensus_tolerance": 0.08,
        "policy_version": "1.0",
    }
    values.update(changes)

    with pytest.raises(InvalidTempoSettingsError):
        TempoEstimationSettings(**cast(Any, values))


def test_automatic_estimate_preserves_method_and_exact_confidence_formula() -> None:
    result = AutomaticTempoEstimate(
        tempo_bpm=120,
        confidence=0.75,
        estimator_name="median_onset_interval",
        estimator_version="1.0",
        confidence_method="octave_equivalent_ioi_consensus_ratio",
        unique_onset_count=5,
        interval_count=4,
        inlier_interval_count=3,
    )

    assert result.tempo_bpm == 120.0
    assert result.confidence == result.inlier_interval_count / result.interval_count == 0.75
    assert result.confidence_method == TEMPO_CONFIDENCE_METHOD


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
def test_invalid_automatic_estimates_are_rejected(changes: dict[str, object]) -> None:
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


def test_selection_source_is_a_string_enum() -> None:
    assert TempoSelectionSource.AUTOMATIC == "automatic"
    assert TempoSelectionSource.MANUAL == "manual"
    assert str(TempoSelectionSource.MANUAL) == "manual"


def test_automatic_resolution_preserves_original_and_estimate() -> None:
    original = written_result()
    automatic = estimate()

    resolution = TempoResolution(
        original=original,
        automatic_estimate=automatic,
        manual_tempo_bpm=None,
        effective_tempo_bpm=120,
        source=TempoSelectionSource.AUTOMATIC,
        revision=1,
    )

    assert resolution.original is original
    assert resolution.automatic_estimate is automatic
    assert resolution.manual_tempo_bpm is None
    assert resolution.effective_tempo_bpm == 120.0
    assert resolution.revision == 1


def test_manual_resolution_can_exist_without_automatic_estimate() -> None:
    original = written_result(())

    resolution = TempoResolution(
        original=original,
        automatic_estimate=None,
        manual_tempo_bpm=90,
        effective_tempo_bpm=90,
        source=TempoSelectionSource.MANUAL,
        revision=1,
    )

    assert resolution.original is original
    assert resolution.automatic_estimate is None
    assert resolution.manual_tempo_bpm == resolution.effective_tempo_bpm == 90.0


@pytest.mark.parametrize(
    "changes",
    [
        {"original": object()},
        {"source": "manual"},
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
        "automatic_estimate": estimate(),
        "manual_tempo_bpm": None,
        "effective_tempo_bpm": 120.0,
        "source": TempoSelectionSource.AUTOMATIC,
        "revision": 1,
        "policy_version": "1.0",
    }
    values.update(changes)

    with pytest.raises(InvalidTempoResolutionError):
        TempoResolution(**cast(Any, values))


def test_tempo_contracts_are_immutable() -> None:
    automatic = estimate()
    resolution = TempoResolution(
        written_result(), automatic, None, 120.0, TempoSelectionSource.AUTOMATIC, 1
    )

    with pytest.raises(FrozenInstanceError):
        automatic.confidence = 0.5  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        resolution.revision = 2  # type: ignore[misc]


def test_tempo_modules_respect_architecture_and_scope_boundaries() -> None:
    domain = (ROOT / "src/saxo_ai/domain/tempo.py").read_text(encoding="utf-8")
    application = (ROOT / "src/saxo_ai/application/tempo_resolution.py").read_text(
        encoding="utf-8"
    )
    infrastructure = (ROOT / "src/saxo_ai/infrastructure/onset_interval_tempo.py").read_text(
        encoding="utf-8"
    )
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    for forbidden in ("fastapi", "mido", "librosa", "numpy", "scipy", "musicxml"):
        assert forbidden not in domain.lower()
    assert "fastapi" not in application.lower()
    assert "mido" not in application.lower()
    assert "onset_seconds" in infrastructure
    assert "Quantized" not in domain + application + infrastructure
    for forbidden_dependency in ("librosa", "aubio", "essentia", "madmom", "numpy", "scipy"):
        assert forbidden_dependency not in pyproject
