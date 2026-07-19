from saxo_ai.domain.models import SaxophoneType

_WRITTEN_PITCH_OFFSETS: dict[SaxophoneType, int] = {
    SaxophoneType.SOPRANO: 2,
    SaxophoneType.ALTO: 9,
    SaxophoneType.TENOR: 14,
    SaxophoneType.BARITONE: 21,
}


def transpose_concert_pitch(concert_pitch: int, saxophone_type: SaxophoneType) -> int:
    """Return the written MIDI pitch for a concert-pitch MIDI note."""
    written_pitch = concert_pitch + _WRITTEN_PITCH_OFFSETS[saxophone_type]
    if not 0 <= written_pitch <= 127:
        raise ValueError("Transposed pitch is outside the MIDI range 0..127.")
    return written_pitch
