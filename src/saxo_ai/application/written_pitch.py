from __future__ import annotations

from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.note_confidence import ConfidenceAnnotatedTranscriptionResult
from saxo_ai.domain.transposition import (
    WrittenPitchOutOfRangeError,
    transpose_concert_pitch,
    written_pitch_offset_for,
)
from saxo_ai.domain.written_pitch import (
    InvalidWrittenPitchContractError,
    WrittenPitchNoteEvent,
    WrittenPitchTranscriptionResult,
)


class TransposeWrittenPitchEvents:
    """Derive written MIDI pitches while retaining the complete concert-pitch chain."""

    def execute(
        self,
        original: ConfidenceAnnotatedTranscriptionResult,
        saxophone_type: SaxophoneType,
    ) -> WrittenPitchTranscriptionResult:
        if not isinstance(original, ConfidenceAnnotatedTranscriptionResult):
            raise InvalidWrittenPitchContractError(
                "original must be a ConfidenceAnnotatedTranscriptionResult"
            )
        written_pitch_offset_for(saxophone_type)

        events: list[WrittenPitchNoteEvent] = []
        for index, source in enumerate(original.annotated_events):
            try:
                written_pitch = transpose_concert_pitch(
                    source.event.pitch_concert_midi,
                    saxophone_type,
                )
            except WrittenPitchOutOfRangeError as error:
                raise error.with_event_index(index) from error
            events.append(
                WrittenPitchNoteEvent(
                    source=source,
                    written_pitch_midi=written_pitch,
                )
            )

        return WrittenPitchTranscriptionResult(
            original=original,
            saxophone_type=saxophone_type,
            events=tuple(events),
        )
