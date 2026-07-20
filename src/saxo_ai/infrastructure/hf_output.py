from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Real
from typing import Any, cast

from saxo_ai.application.transcription_errors import (
    InvalidTranscriptionEngineOutputError,
)
from saxo_ai.domain.note_events import InvalidNoteEventError, NoteEvent, NoteEventBatch
from saxo_ai.infrastructure.hf_baseline_contract import (
    BEGIN_MIDI_NOTE,
    FRAMES_PER_SECOND,
)


def convert_baseline_output(external_output: object) -> NoteEventBatch:
    if not isinstance(external_output, dict):
        raise InvalidTranscriptionEngineOutputError("baseline output must be an object")
    raw_events = external_output.get("est_note_events")
    raw_output_dict = external_output.get("output_dict")
    if not isinstance(raw_events, list):
        raise InvalidTranscriptionEngineOutputError("est_note_events must be a list")
    if not isinstance(raw_output_dict, dict):
        raise InvalidTranscriptionEngineOutputError("output_dict must be an object")
    if "reg_onset_output" not in raw_output_dict:
        raise InvalidTranscriptionEngineOutputError(
            "output_dict.reg_onset_output is required"
        )
    onset_matrix = _OnsetMatrix(raw_output_dict["reg_onset_output"])
    notes = tuple(
        _convert_event(raw_event, onset_matrix, index)
        for index, raw_event in enumerate(raw_events)
    )
    ordered = tuple(
        sorted(
            notes,
            key=lambda event: (
                event.onset_seconds,
                event.pitch_concert_midi,
                event.offset_seconds,
                event.velocity,
            ),
        )
    )
    return NoteEventBatch(events=ordered)


def _convert_event(raw_event: object, matrix: _OnsetMatrix, index: int) -> NoteEvent:
    if not isinstance(raw_event, dict):
        raise InvalidTranscriptionEngineOutputError(
            "event must be an object",
            event_index=index,
        )
    required = ("onset_time", "offset_time", "midi_note", "velocity")
    missing = [field for field in required if field not in raw_event]
    if missing:
        raise InvalidTranscriptionEngineOutputError(
            f"missing required field(s): {', '.join(missing)}",
            event_index=index,
        )
    try:
        onset = raw_event["onset_time"]
        pitch = raw_event["midi_note"]
        return NoteEvent(
            pitch_concert_midi=pitch,
            onset_seconds=onset,
            offset_seconds=raw_event["offset_time"],
            velocity=raw_event["velocity"],
            confidence=matrix.confidence(onset=onset, pitch=pitch),
        )
    except (InvalidNoteEventError, ValueError, TypeError) as error:
        raise InvalidTranscriptionEngineOutputError(
            str(error),
            event_index=index,
        ) from error


class _OnsetMatrix:
    def __init__(self, matrix: object) -> None:
        self._matrix = matrix
        shape = getattr(matrix, "shape", None)
        if shape is not None:
            if not isinstance(shape, Sequence) or len(shape) != 2:
                raise InvalidTranscriptionEngineOutputError(
                    "reg_onset_output must be a two-dimensional matrix"
                )
            self._frames = int(shape[0])
            self._pitches = int(shape[1])
            self._numpy_style = True
        elif isinstance(matrix, (list, tuple)):
            if not matrix or not all(isinstance(row, (list, tuple)) for row in matrix):
                raise InvalidTranscriptionEngineOutputError(
                    "reg_onset_output must be a non-empty two-dimensional matrix"
                )
            rows = cast(Sequence[Sequence[object]], matrix)
            self._frames = len(rows)
            self._pitches = len(rows[0])
            if self._pitches == 0 or any(len(row) != self._pitches for row in rows):
                raise InvalidTranscriptionEngineOutputError(
                    "reg_onset_output rows must have a consistent positive width"
                )
            self._numpy_style = False
        else:
            raise InvalidTranscriptionEngineOutputError(
                "reg_onset_output must be a two-dimensional matrix"
            )
        if self._frames <= 0 or self._pitches <= 0:
            raise InvalidTranscriptionEngineOutputError(
                "reg_onset_output must contain frames and pitch classes"
            )

    def confidence(self, *, onset: object, pitch: object) -> float:
        if isinstance(onset, bool) or not isinstance(onset, Real):
            raise ValueError("onset_time must be a finite number")
        onset_value = float(onset)
        if not math.isfinite(onset_value) or onset_value < 0:
            raise ValueError("onset_time must be a finite non-negative number")
        if isinstance(pitch, bool) or not isinstance(pitch, int):
            raise ValueError("midi_note must be a Python integer")
        pitch_index = pitch - BEGIN_MIDI_NOTE
        if not 0 <= pitch_index < self._pitches:
            raise ValueError("midi_note has no corresponding onset activation")
        center_frame = round(onset_value * FRAMES_PER_SECOND)
        window_start = max(0, center_frame - 2)
        window_end = min(self._frames, center_frame + 3)
        if window_start >= window_end:
            raise ValueError("onset activation window contains no frames")
        return max(
            self._value(frame, pitch_index) for frame in range(window_start, window_end)
        )

    def _value(self, frame: int, pitch: int) -> float:
        try:
            matrix = cast(Any, self._matrix)
            raw = matrix[frame, pitch] if self._numpy_style else matrix[frame][pitch]
        except Exception as error:
            raise ValueError("onset activation could not be indexed") from error
        if isinstance(raw, bool) or not isinstance(raw, Real):
            raise ValueError("onset activation must be numeric")
        value = float(raw)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("onset activation must be finite and between 0.0 and 1.0")
        return value
