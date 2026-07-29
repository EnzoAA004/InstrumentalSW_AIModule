from __future__ import annotations

import pytest

from saxo_ai.application.note_transcription_evaluation import EvaluateNoteTranscription
from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.note_transcription_metrics import NoteMatchToleranceSettings


def note(
    pitch: int = 60,
    onset: float = 0.0,
    offset: float | None = None,
    velocity: int = 90,
    confidence: float = 0.9,
) -> NoteEvent:
    return NoteEvent(
        pitch_concert_midi=pitch,
        onset_seconds=onset,
        offset_seconds=offset if offset is not None else onset + 0.5,
        velocity=velocity,
        confidence=confidence,
    )


def batch(*events: NoteEvent) -> NoteEventBatch:
    return NoteEventBatch(events=events)


class TestEvaluateNoteTranscription:
    def test_identical_batches_are_perfect(self) -> None:
        events = batch(note(pitch=60, onset=0.0), note(pitch=64, onset=1.0))
        result = EvaluateNoteTranscription().execute(reference=events, estimated=events)

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1_score == 1.0
        assert result.matched_count == 2
        assert result.mean_onset_error_seconds == pytest.approx(0.0)
        assert result.median_onset_error_seconds == pytest.approx(0.0)

    def test_both_empty_is_perfect_by_convention(self) -> None:
        result = EvaluateNoteTranscription().execute(reference=batch(), estimated=batch())

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1_score == 1.0
        assert result.matched_count == 0
        assert result.mean_onset_error_seconds is None

    def test_missed_all_reference_notes(self) -> None:
        reference = batch(note(pitch=60, onset=0.0), note(pitch=64, onset=1.0))
        result = EvaluateNoteTranscription().execute(reference=reference, estimated=batch())

        assert result.matched_count == 0
        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1_score == 0.0

    def test_only_false_positives(self) -> None:
        estimated = batch(note(pitch=60, onset=0.0), note(pitch=64, onset=1.0))
        result = EvaluateNoteTranscription().execute(reference=batch(), estimated=estimated)

        assert result.matched_count == 0
        assert result.precision == 0.0
        assert result.recall == 0.0

    def test_different_pitch_never_matches_even_with_identical_timing(self) -> None:
        reference = batch(note(pitch=60, onset=0.0))
        estimated = batch(note(pitch=61, onset=0.0))
        result = EvaluateNoteTranscription().execute(reference=reference, estimated=estimated)

        assert result.matched_count == 0

    def test_onset_within_tolerance_matches(self) -> None:
        reference = batch(note(pitch=60, onset=1.000))
        estimated = batch(note(pitch=60, onset=1.049))
        result = EvaluateNoteTranscription(
            tolerance=NoteMatchToleranceSettings(onset_tolerance_seconds=0.05)
        ).execute(reference=reference, estimated=estimated)

        assert result.matched_count == 1
        assert result.mean_onset_error_seconds == pytest.approx(0.049)

    def test_onset_outside_tolerance_does_not_match(self) -> None:
        reference = batch(note(pitch=60, onset=1.000))
        estimated = batch(note(pitch=60, onset=1.100))
        result = EvaluateNoteTranscription(
            tolerance=NoteMatchToleranceSettings(onset_tolerance_seconds=0.05)
        ).execute(reference=reference, estimated=estimated)

        assert result.matched_count == 0

    def test_greedy_matching_does_not_double_match_one_estimate(self) -> None:
        reference = batch(note(pitch=60, onset=0.0), note(pitch=60, onset=0.1, offset=0.6))
        estimated = batch(note(pitch=60, onset=0.05))
        result = EvaluateNoteTranscription(
            tolerance=NoteMatchToleranceSettings(onset_tolerance_seconds=0.05)
        ).execute(reference=reference, estimated=estimated)

        assert result.matched_count == 1
        assert result.reference_count == 2
        assert result.estimated_count == 1

    def test_offset_evaluation_rejects_mismatched_duration(self) -> None:
        reference = batch(note(pitch=60, onset=0.0, offset=0.5))
        estimated = batch(note(pitch=60, onset=0.0, offset=2.0))
        result = EvaluateNoteTranscription(
            tolerance=NoteMatchToleranceSettings(evaluate_offset=True)
        ).execute(reference=reference, estimated=estimated)

        assert result.matched_count == 0

    def test_offset_evaluation_accepts_matching_duration(self) -> None:
        reference = batch(note(pitch=60, onset=0.0, offset=0.5))
        estimated = batch(note(pitch=60, onset=0.0, offset=0.52))
        result = EvaluateNoteTranscription(
            tolerance=NoteMatchToleranceSettings(evaluate_offset=True)
        ).execute(reference=reference, estimated=estimated)

        assert result.matched_count == 1

    def test_result_is_deterministic(self) -> None:
        reference = batch(note(pitch=60, onset=0.0), note(pitch=64, onset=1.0))
        estimated = batch(note(pitch=60, onset=0.01), note(pitch=64, onset=1.03))
        use_case = EvaluateNoteTranscription()

        first = use_case.execute(reference=reference, estimated=estimated)
        second = use_case.execute(reference=reference, estimated=estimated)

        assert first == second
