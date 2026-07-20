from __future__ import annotations

from saxo_ai.domain.models import SaxophoneType

_WRITTEN_PITCH_OFFSETS: dict[SaxophoneType, int] = {
    SaxophoneType.SOPRANO: 2,
    SaxophoneType.ALTO: 9,
    SaxophoneType.TENOR: 14,
    SaxophoneType.BARITONE: 21,
}


class InvalidConcertPitchError(ValueError):
    """Raised when a concert pitch is not a valid Python MIDI integer."""

    def __init__(self, concert_pitch_midi: object) -> None:
        super().__init__("concert_pitch_midi must be an integer between 0 and 127")
        self.concert_pitch_midi = concert_pitch_midi


class InvalidSaxophoneTypeError(ValueError):
    """Raised when written-pitch transposition receives an unknown instrument type."""

    def __init__(self, saxophone_type: object) -> None:
        super().__init__("saxophone_type must be a SaxophoneType")
        self.saxophone_type = saxophone_type


class WrittenPitchOutOfRangeError(ValueError):
    """Raised when a valid concert pitch cannot be written inside MIDI range."""

    def __init__(
        self,
        *,
        saxophone_type: SaxophoneType,
        concert_pitch_midi: int,
        written_offset_semitones: int,
        attempted_written_pitch_midi: int,
        event_index: int | None = None,
    ) -> None:
        location = "" if event_index is None else f" at event index {event_index}"
        super().__init__(
            f"Written pitch {attempted_written_pitch_midi}{location} is outside the MIDI range "
            "0..127."
        )
        self.saxophone_type = saxophone_type
        self.concert_pitch_midi = concert_pitch_midi
        self.written_offset_semitones = written_offset_semitones
        self.attempted_written_pitch_midi = attempted_written_pitch_midi
        self.event_index = event_index

    def with_event_index(self, event_index: int) -> WrittenPitchOutOfRangeError:
        """Return the same controlled failure enriched with its batch position."""

        return WrittenPitchOutOfRangeError(
            saxophone_type=self.saxophone_type,
            concert_pitch_midi=self.concert_pitch_midi,
            written_offset_semitones=self.written_offset_semitones,
            attempted_written_pitch_midi=self.attempted_written_pitch_midi,
            event_index=event_index,
        )


def written_pitch_offset_for(saxophone_type: SaxophoneType) -> int:
    """Return the single documented written-pitch offset for a saxophone type."""

    if not isinstance(saxophone_type, SaxophoneType):
        raise InvalidSaxophoneTypeError(saxophone_type)
    return _WRITTEN_PITCH_OFFSETS[saxophone_type]


def _validate_concert_pitch(concert_pitch: object) -> int:
    if isinstance(concert_pitch, bool) or not isinstance(concert_pitch, int):
        raise InvalidConcertPitchError(concert_pitch)
    if not 0 <= concert_pitch <= 127:
        raise InvalidConcertPitchError(concert_pitch)
    return concert_pitch


def transpose_concert_pitch(concert_pitch: int, saxophone_type: SaxophoneType) -> int:
    """Return the written MIDI pitch for a validated concert-pitch MIDI note."""

    validated_pitch = _validate_concert_pitch(concert_pitch)
    offset = written_pitch_offset_for(saxophone_type)
    written_pitch = validated_pitch + offset
    if not 0 <= written_pitch <= 127:
        raise WrittenPitchOutOfRangeError(
            saxophone_type=saxophone_type,
            concert_pitch_midi=validated_pitch,
            written_offset_semitones=offset,
            attempted_written_pitch_midi=written_pitch,
        )
    return written_pitch
