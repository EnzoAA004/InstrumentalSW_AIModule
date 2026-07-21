from __future__ import annotations

import math
import statistics

from saxo_ai.application.tempo_resolution import TempoEstimator
from saxo_ai.domain.tempo import (
    TEMPO_CONFIDENCE_METHOD,
    TEMPO_ESTIMATOR_NAME,
    TEMPO_ESTIMATOR_VERSION,
    AutomaticTempoEstimate,
    InvalidTempoEstimateError,
    InvalidTempoSettingsError,
    TempoEstimationSettings,
    TempoEstimationUnavailableError,
)
from saxo_ai.domain.written_pitch import WrittenPitchTranscriptionResult


def _octave_equivalents_in_range(
    bpm: float,
    *,
    minimum_bpm: float,
    maximum_bpm: float,
) -> tuple[float, ...]:
    candidate = bpm
    while candidate > maximum_bpm:
        candidate /= 2.0
    while candidate / 2.0 >= minimum_bpm:
        candidate /= 2.0
    while candidate < minimum_bpm:
        candidate *= 2.0
        if not math.isfinite(candidate) or candidate > maximum_bpm:
            return ()
    equivalents: list[float] = []
    while candidate <= maximum_bpm:
        equivalents.append(candidate)
        candidate *= 2.0
        if not math.isfinite(candidate):
            break
    return tuple(equivalents)


def _resolve_octave_equivalent(
    bpm: float,
    *,
    minimum_bpm: float,
    maximum_bpm: float,
) -> float | None:
    if minimum_bpm <= bpm <= maximum_bpm:
        return bpm
    candidate = bpm
    if candidate < minimum_bpm:
        while candidate < minimum_bpm:
            candidate *= 2.0
            if not math.isfinite(candidate):
                return None
    else:
        while candidate > maximum_bpm:
            candidate /= 2.0
    return candidate if minimum_bpm <= candidate <= maximum_bpm else None


def _closest_octave_equivalent(
    bpm: float,
    *,
    target_bpm: float,
    minimum_bpm: float,
    maximum_bpm: float,
) -> float | None:
    equivalents = _octave_equivalents_in_range(
        bpm,
        minimum_bpm=minimum_bpm,
        maximum_bpm=maximum_bpm,
    )
    if not equivalents:
        return None
    return min(equivalents, key=lambda value: (abs(value - target_bpm), value))


class OnsetIntervalTempoEstimator(TempoEstimator):
    """Deterministic O(n log n) median inter-onset-interval baseline."""

    def estimate(
        self,
        original: WrittenPitchTranscriptionResult,
        settings: TempoEstimationSettings,
    ) -> AutomaticTempoEstimate:
        if not isinstance(original, WrittenPitchTranscriptionResult):
            raise InvalidTempoEstimateError(
                "original must be a WrittenPitchTranscriptionResult"
            )
        if not isinstance(settings, TempoEstimationSettings):
            raise InvalidTempoSettingsError(
                "settings must be TempoEstimationSettings"
            )

        unique_onsets = tuple(
            sorted({event.source.event.onset_seconds for event in original.events})
        )
        intervals = tuple(
            later - earlier
            for earlier, later in zip(unique_onsets, unique_onsets[1:], strict=False)
            if later - earlier > 0.0
        )
        interval_count = len(intervals)
        if interval_count < settings.minimum_interval_count:
            raise TempoEstimationUnavailableError(
                "Insufficient unique note onsets for automatic tempo estimation.",
                unique_onset_count=len(unique_onsets),
                interval_count=interval_count,
                minimum_interval_count=settings.minimum_interval_count,
            )

        candidates = tuple(60.0 / interval for interval in intervals)
        median_candidate = float(statistics.median(candidates))
        estimated_bpm = _resolve_octave_equivalent(
            median_candidate,
            minimum_bpm=settings.minimum_bpm,
            maximum_bpm=settings.maximum_bpm,
        )
        if estimated_bpm is None:
            raise TempoEstimationUnavailableError(
                "No octave-equivalent tempo candidate is inside the configured range.",
                unique_onset_count=len(unique_onsets),
                interval_count=interval_count,
                minimum_interval_count=settings.minimum_interval_count,
            )

        inlier_count = 0
        for candidate in candidates:
            equivalent = _closest_octave_equivalent(
                candidate,
                target_bpm=estimated_bpm,
                minimum_bpm=settings.minimum_bpm,
                maximum_bpm=settings.maximum_bpm,
            )
            if equivalent is None:
                continue
            relative_error = abs(equivalent - estimated_bpm) / estimated_bpm
            if relative_error <= settings.consensus_tolerance:
                inlier_count += 1

        return AutomaticTempoEstimate(
            tempo_bpm=estimated_bpm,
            confidence=inlier_count / interval_count,
            estimator_name=TEMPO_ESTIMATOR_NAME,
            estimator_version=TEMPO_ESTIMATOR_VERSION,
            confidence_method=TEMPO_CONFIDENCE_METHOD,
            unique_onset_count=len(unique_onsets),
            interval_count=interval_count,
            inlier_interval_count=inlier_count,
        )
