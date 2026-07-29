from __future__ import annotations

import pytest

from saxo_ai.domain.note_transcription_metrics import (
    InvalidNoteMatchToleranceError,
    InvalidNoteTranscriptionMetricsError,
    NoteMatchToleranceSettings,
    NoteTranscriptionMetrics,
)


def metrics(
    *,
    matched_count: int = 1,
    reference_count: int = 1,
    estimated_count: int = 1,
    mean_onset_error_seconds: float | None = 0.01,
    median_onset_error_seconds: float | None = 0.01,
) -> NoteTranscriptionMetrics:
    return NoteTranscriptionMetrics(
        tolerance=NoteMatchToleranceSettings(),
        reference_count=reference_count,
        estimated_count=estimated_count,
        matched_count=matched_count,
        precision=1.0,
        recall=1.0,
        f1_score=1.0,
        mean_onset_error_seconds=mean_onset_error_seconds,
        median_onset_error_seconds=median_onset_error_seconds,
    )


class TestNoteMatchToleranceSettings:
    def test_accepts_defaults(self) -> None:
        settings = NoteMatchToleranceSettings()
        assert settings.onset_tolerance_seconds == pytest.approx(0.05)
        assert settings.evaluate_offset is False

    def test_rejects_non_positive_onset_tolerance(self) -> None:
        with pytest.raises(InvalidNoteMatchToleranceError):
            NoteMatchToleranceSettings(onset_tolerance_seconds=0.0)

    def test_rejects_offset_ratio_above_one(self) -> None:
        with pytest.raises(InvalidNoteMatchToleranceError):
            NoteMatchToleranceSettings(offset_ratio=1.5)

    def test_rejects_non_boolean_evaluate_offset(self) -> None:
        with pytest.raises(InvalidNoteMatchToleranceError):
            NoteMatchToleranceSettings(evaluate_offset="yes")  # type: ignore[arg-type]

    def test_rejects_non_positive_offset_min_tolerance(self) -> None:
        with pytest.raises(InvalidNoteMatchToleranceError):
            NoteMatchToleranceSettings(offset_min_tolerance_seconds=-1.0)


class TestNoteTranscriptionMetrics:
    def test_accepts_consistent_result(self) -> None:
        value = metrics()
        assert value.matched_count == 1

    def test_rejects_matched_count_above_minimum(self) -> None:
        with pytest.raises(InvalidNoteTranscriptionMetricsError):
            metrics(matched_count=5, reference_count=1, estimated_count=10)

    def test_rejects_out_of_range_precision(self) -> None:
        with pytest.raises(InvalidNoteTranscriptionMetricsError):
            NoteTranscriptionMetrics(
                tolerance=NoteMatchToleranceSettings(),
                reference_count=1,
                estimated_count=1,
                matched_count=1,
                precision=1.5,
                recall=1.0,
                f1_score=1.0,
                mean_onset_error_seconds=0.0,
                median_onset_error_seconds=0.0,
            )

    def test_rejects_onset_error_present_without_matches(self) -> None:
        with pytest.raises(InvalidNoteTranscriptionMetricsError):
            metrics(matched_count=0, mean_onset_error_seconds=0.01, median_onset_error_seconds=0.01)

    def test_rejects_missing_onset_error_with_matches(self) -> None:
        with pytest.raises(InvalidNoteTranscriptionMetricsError):
            metrics(matched_count=1, mean_onset_error_seconds=None, median_onset_error_seconds=None)

    def test_zero_matches_allows_none_errors(self) -> None:
        value = metrics(
            matched_count=0,
            reference_count=0,
            estimated_count=0,
            mean_onset_error_seconds=None,
            median_onset_error_seconds=None,
        )
        assert value.mean_onset_error_seconds is None
