from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from saxo_ai.domain.rhythm_quantization import (
    InvalidQuantizedNoteError,
    InvalidQuantizedRestError,
    InvalidQuantizedRhythmResultError,
    InvalidRhythmQuantizationReportError,
    InvalidRhythmQuantizationSettingsError,
    QuantizedNoteEvent,
    QuantizedRest,
    QuantizedRhythmResult,
    QuantizedTimelineItem,
    RhythmQuantizationReport,
    RhythmQuantizationSettings,
)
from saxo_ai.domain.tempo import TempoResolution, normalize_positive_bpm
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent


class RhythmQuantizationError(RuntimeError):
    """Raised when monophonic rhythm quantization fails unexpectedly."""


def _positive_subdivision_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidRhythmQuantizationSettingsError(
            "subdivisions_per_beat must be a positive integer"
        )
    return value


def _round_decimal_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def round_grid_position_half_up(value: float) -> int:
    """Round a non-negative grid position with midpoint ties moving forward."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RhythmQuantizationError("Grid position must be a finite non-negative number.")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise RhythmQuantizationError("Grid position must be a finite non-negative number.")
    return _round_decimal_half_up(Decimal(str(normalized)))


def seconds_per_grid_step(
    tempo_bpm: object,
    subdivisions_per_beat: object,
) -> float:
    tempo = normalize_positive_bpm(tempo_bpm)
    subdivisions = _positive_subdivision_count(subdivisions_per_beat)
    return float(Decimal("60") / Decimal(str(tempo)) / Decimal(subdivisions))


def seconds_to_grid_step(
    seconds: object,
    tempo_bpm: object,
    subdivisions_per_beat: object,
) -> int:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise RhythmQuantizationError("Seconds must be a finite non-negative number.")
    normalized_seconds = float(seconds)
    if not math.isfinite(normalized_seconds) or normalized_seconds < 0.0:
        raise RhythmQuantizationError("Seconds must be a finite non-negative number.")
    tempo = normalize_positive_bpm(tempo_bpm)
    subdivisions = _positive_subdivision_count(subdivisions_per_beat)
    grid_position = (
        Decimal(str(normalized_seconds))
        * Decimal(str(tempo))
        / Decimal("60")
        * Decimal(subdivisions)
    )
    return _round_decimal_half_up(grid_position)


def grid_step_to_seconds(
    grid_step: object,
    tempo_bpm: object,
    subdivisions_per_beat: object,
) -> float:
    if isinstance(grid_step, bool) or not isinstance(grid_step, int) or grid_step < 0:
        raise RhythmQuantizationError("grid_step must be a non-negative integer")
    tempo = normalize_positive_bpm(tempo_bpm)
    subdivisions = _positive_subdivision_count(subdivisions_per_beat)
    return float(Decimal(grid_step) * Decimal("60") / Decimal(str(tempo)) / Decimal(subdivisions))


@dataclass(slots=True)
class _WorkingNote:
    source: WrittenPitchNoteEvent
    source_index: int
    onset_step: int
    offset_step: int
    minimum_duration_adjusted: bool = False
    overlap_adjusted: bool = False


def _candidate_notes(
    tempo: TempoResolution,
    settings: RhythmQuantizationSettings,
) -> list[_WorkingNote]:
    candidates: list[_WorkingNote] = []
    for source_index, source in enumerate(tempo.original.events):
        original = source.source.event
        onset_step = seconds_to_grid_step(
            original.onset_seconds,
            tempo.effective_tempo_bpm,
            settings.subdivisions_per_beat,
        )
        offset_step = seconds_to_grid_step(
            original.offset_seconds,
            tempo.effective_tempo_bpm,
            settings.subdivisions_per_beat,
        )
        minimum_adjusted = offset_step <= onset_step
        if minimum_adjusted:
            offset_step = onset_step + 1
        candidates.append(
            _WorkingNote(
                source=source,
                source_index=source_index,
                onset_step=onset_step,
                offset_step=offset_step,
                minimum_duration_adjusted=minimum_adjusted,
            )
        )
    candidates.sort(
        key=lambda candidate: (
            candidate.source.source.event.onset_seconds,
            candidate.source.source.event.offset_seconds,
            candidate.source.source.event.pitch_concert_midi,
            candidate.source_index,
        )
    )
    return candidates


def _resolve_monophonic_overlaps(
    candidates: list[_WorkingNote],
) -> list[_WorkingNote]:
    resolved: list[_WorkingNote] = []
    for current in candidates:
        if not resolved:
            resolved.append(current)
            continue
        previous = resolved[-1]
        if current.onset_step >= previous.offset_step:
            resolved.append(current)
            continue
        if previous.onset_step < current.onset_step:
            previous.offset_step = current.onset_step
            previous.overlap_adjusted = True
            resolved.append(current)
            continue
        current.onset_step = previous.offset_step
        current.offset_step = max(current.offset_step, current.onset_step + 1)
        current.overlap_adjusted = True
        resolved.append(current)
    return resolved


def _finalize_notes(
    working_notes: list[_WorkingNote],
    tempo: TempoResolution,
    settings: RhythmQuantizationSettings,
) -> tuple[QuantizedNoteEvent, ...]:
    notes: list[QuantizedNoteEvent] = []
    for working in working_notes:
        original = working.source.source.event
        quantized_onset_seconds = grid_step_to_seconds(
            working.onset_step,
            tempo.effective_tempo_bpm,
            settings.subdivisions_per_beat,
        )
        quantized_offset_seconds = grid_step_to_seconds(
            working.offset_step,
            tempo.effective_tempo_bpm,
            settings.subdivisions_per_beat,
        )
        notes.append(
            QuantizedNoteEvent(
                source=working.source,
                source_index=working.source_index,
                quantized_onset_step=working.onset_step,
                quantized_offset_step=working.offset_step,
                onset_delta_seconds=quantized_onset_seconds - original.onset_seconds,
                offset_delta_seconds=quantized_offset_seconds - original.offset_seconds,
            )
        )
    return tuple(notes)


def _build_timeline(
    notes: tuple[QuantizedNoteEvent, ...],
) -> tuple[QuantizedTimelineItem, ...]:
    timeline: list[QuantizedTimelineItem] = []
    cursor = 0
    for note in notes:
        if note.quantized_onset_step > cursor:
            timeline.append(QuantizedRest(cursor, note.quantized_onset_step))
        timeline.append(note)
        cursor = note.quantized_offset_step
    return tuple(timeline)


def _build_report(
    settings: RhythmQuantizationSettings,
    working_notes: list[_WorkingNote],
    notes: tuple[QuantizedNoteEvent, ...],
    timeline: tuple[QuantizedTimelineItem, ...],
) -> RhythmQuantizationReport:
    onset_total = math.fsum(abs(note.onset_delta_seconds) for note in notes)
    offset_total = math.fsum(abs(note.offset_delta_seconds) for note in notes)
    maximum = max(
        (
            abs(delta)
            for note in notes
            for delta in (note.onset_delta_seconds, note.offset_delta_seconds)
        ),
        default=0.0,
    )
    return RhythmQuantizationReport(
        settings=settings,
        input_event_count=len(working_notes),
        quantized_note_count=len(notes),
        rest_count=sum(isinstance(item, QuantizedRest) for item in timeline),
        minimum_duration_adjustment_count=sum(
            note.minimum_duration_adjusted for note in working_notes
        ),
        overlap_adjusted_event_count=sum(note.overlap_adjusted for note in working_notes),
        total_absolute_onset_delta_seconds=onset_total,
        total_absolute_offset_delta_seconds=offset_total,
        maximum_absolute_boundary_delta_seconds=maximum,
    )


_CONTROLLED_ERRORS = (
    InvalidRhythmQuantizationSettingsError,
    InvalidQuantizedNoteError,
    InvalidQuantizedRestError,
    InvalidRhythmQuantizationReportError,
    InvalidQuantizedRhythmResultError,
    RhythmQuantizationError,
)


class QuantizeMonophonicRhythm:
    def execute(
        self,
        tempo: TempoResolution,
        settings: RhythmQuantizationSettings,
    ) -> QuantizedRhythmResult:
        if not isinstance(tempo, TempoResolution):
            raise InvalidQuantizedRhythmResultError("tempo must be a TempoResolution")
        if not isinstance(settings, RhythmQuantizationSettings):
            raise InvalidRhythmQuantizationSettingsError(
                "settings must be RhythmQuantizationSettings"
            )
        try:
            working = _resolve_monophonic_overlaps(_candidate_notes(tempo, settings))
            notes = _finalize_notes(working, tempo, settings)
            timeline = _build_timeline(notes)
            report = _build_report(settings, working, notes, timeline)
            return QuantizedRhythmResult(
                tempo=tempo,
                timeline=timeline,
                report=report,
            )
        except _CONTROLLED_ERRORS:
            raise
        except Exception as error:
            raise RhythmQuantizationError("Rhythm quantization failed.") from error
