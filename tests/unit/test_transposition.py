import pytest

from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.transposition import transpose_concert_pitch


@pytest.mark.parametrize(
    ("saxophone_type", "expected_written_pitch"),
    [
        (SaxophoneType.SOPRANO, 62),
        (SaxophoneType.ALTO, 69),
        (SaxophoneType.TENOR, 74),
        (SaxophoneType.BARITONE, 81),
    ],
)
def test_transpose_concert_pitch_applies_saxophone_offset(
    saxophone_type: SaxophoneType,
    expected_written_pitch: int,
) -> None:
    assert transpose_concert_pitch(60, saxophone_type) == expected_written_pitch


def test_transpose_concert_pitch_rejects_result_outside_midi_range() -> None:
    with pytest.raises(ValueError, match="outside the MIDI range"):
        transpose_concert_pitch(120, SaxophoneType.BARITONE)
