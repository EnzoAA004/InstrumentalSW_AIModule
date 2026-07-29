from __future__ import annotations

import math
import statistics

from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.note_transcription_metrics import (
    NoteMatchToleranceSettings,
    NoteTranscriptionMetrics,
)


def _offset_tolerance(tolerance: NoteMatchToleranceSettings, reference: NoteEvent) -> float:
    return max(
        tolerance.offset_ratio * reference.duration_seconds,
        tolerance.offset_min_tolerance_seconds,
    )


def _is_within_tolerance(
    *, tolerance: NoteMatchToleranceSettings, reference: NoteEvent, candidate: NoteEvent
) -> bool:
    if abs(candidate.onset_seconds - reference.onset_seconds) > tolerance.onset_tolerance_seconds:
        return False
    if not tolerance.evaluate_offset:
        return True
    return abs(candidate.offset_seconds - reference.offset_seconds) <= _offset_tolerance(
        tolerance, reference
    )


def _match_pitch_group(
    *,
    tolerance: NoteMatchToleranceSettings,
    reference_events: list[NoteEvent],
    estimated_events: list[NoteEvent],
) -> list[float]:
    """Greedy nearest-onset one-to-one matching within one MIDI pitch."""

    remaining_estimated = sorted(estimated_events, key=lambda event: event.onset_seconds)
    onset_errors: list[float] = []
    for reference in sorted(reference_events, key=lambda event: event.onset_seconds):
        best_index: int | None = None
        best_error = math.inf
        for index, candidate in enumerate(remaining_estimated):
            if not _is_within_tolerance(
                tolerance=tolerance, reference=reference, candidate=candidate
            ):
                continue
            error = abs(candidate.onset_seconds - reference.onset_seconds)
            if error < best_error:
                best_error = error
                best_index = index
        if best_index is not None:
            onset_errors.append(best_error)
            del remaining_estimated[best_index]
    return onset_errors


class EvaluateNoteTranscription:
    """Note-level precision/recall/F1 and onset-timing error against a reference batch."""

    def __init__(self, *, tolerance: NoteMatchToleranceSettings | None = None) -> None:
        self._tolerance = tolerance or NoteMatchToleranceSettings()

    def execute(
        self, *, reference: NoteEventBatch, estimated: NoteEventBatch
    ) -> NoteTranscriptionMetrics:
        reference_by_pitch: dict[int, list[NoteEvent]] = {}
        for event in reference.events:
            reference_by_pitch.setdefault(event.pitch_concert_midi, []).append(event)
        estimated_by_pitch: dict[int, list[NoteEvent]] = {}
        for event in estimated.events:
            estimated_by_pitch.setdefault(event.pitch_concert_midi, []).append(event)

        onset_errors: list[float] = []
        for pitch in reference_by_pitch.keys() | estimated_by_pitch.keys():
            onset_errors.extend(
                _match_pitch_group(
                    tolerance=self._tolerance,
                    reference_events=reference_by_pitch.get(pitch, []),
                    estimated_events=estimated_by_pitch.get(pitch, []),
                )
            )

        reference_count = len(reference.events)
        estimated_count = len(estimated.events)
        matched_count = len(onset_errors)

        if reference_count == 0 and estimated_count == 0:
            precision = recall = f1_score = 1.0
        else:
            precision = matched_count / estimated_count if estimated_count else 0.0
            recall = matched_count / reference_count if reference_count else 0.0
            f1_score = (
                2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            )

        return NoteTranscriptionMetrics(
            tolerance=self._tolerance,
            reference_count=reference_count,
            estimated_count=estimated_count,
            matched_count=matched_count,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            mean_onset_error_seconds=statistics.mean(onset_errors) if onset_errors else None,
            median_onset_error_seconds=statistics.median(onset_errors) if onset_errors else None,
        )
