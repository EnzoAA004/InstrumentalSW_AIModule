from typing import Any, cast

import pytest

from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.transposition import (
    InvalidConcertPitchError,
    InvalidSaxophoneTypeError,
    WrittenPitchOutOfRangeError,
    transpose_concert_pitch,
)


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


@pytest.mark.parametrize(
    ("saxophone_type", "maximum_concert_pitch"),
    [
        (SaxophoneType.SOPRANO, 125),
        (SaxophoneType.ALTO, 118),
        (SaxophoneType.TENOR, 113),
        (SaxophoneType.BARITONE, 106),
    ],
)
def test_transpose_concert_pitch_accepts_exact_written_midi_maximum(
    saxophone_type: SaxophoneType,
    maximum_concert_pitch: int,
) -> None:
    assert transpose_concert_pitch(maximum_concert_pitch, saxophone_type) == 127


@pytest.mark.parametrize(
    ("saxophone_type", "expected_written_pitch"),
    [
        (SaxophoneType.SOPRANO, 2),
        (SaxophoneType.ALTO, 9),
        (SaxophoneType.TENOR, 14),
        (SaxophoneType.BARITONE, 21),
    ],
)
def test_transpose_concert_pitch_accepts_concert_midi_zero(
    saxophone_type: SaxophoneType,
    expected_written_pitch: int,
) -> None:
    assert transpose_concert_pitch(0, saxophone_type) == expected_written_pitch


@pytest.mark.parametrize("concert_pitch", [-1, 128, 60.0, True, False, "60", None])
def test_transpose_concert_pitch_rejects_invalid_concert_pitch(concert_pitch: object) -> None:
    with pytest.raises(InvalidConcertPitchError) as captured:
        transpose_concert_pitch(cast(Any, concert_pitch), SaxophoneType.ALTO)

    assert captured.value.concert_pitch_midi is concert_pitch


@pytest.mark.parametrize("saxophone_type", ["alto", "ALTO", object(), None])
def test_transpose_concert_pitch_rejects_invalid_saxophone_type(
    saxophone_type: object,
) -> None:
    with pytest.raises(InvalidSaxophoneTypeError) as captured:
        transpose_concert_pitch(60, cast(Any, saxophone_type))

    assert captured.value.saxophone_type is saxophone_type


@pytest.mark.parametrize(
    ("saxophone_type", "concert_pitch", "offset"),
    [
        (SaxophoneType.SOPRANO, 126, 2),
        (SaxophoneType.ALTO, 119, 9),
        (SaxophoneType.TENOR, 114, 14),
        (SaxophoneType.BARITONE, 107, 21),
    ],
)
def test_transpose_concert_pitch_rejects_written_pitch_above_midi_maximum(
    saxophone_type: SaxophoneType,
    concert_pitch: int,
    offset: int,
) -> None:
    with pytest.raises(WrittenPitchOutOfRangeError) as captured:
        transpose_concert_pitch(concert_pitch, saxophone_type)

    error = captured.value
    assert error.saxophone_type is saxophone_type
    assert error.concert_pitch_midi == concert_pitch
    assert error.written_offset_semitones == offset
    assert error.attempted_written_pitch_midi == 128
    assert error.event_index is None
    assert "128" in str(error)
    assert "0..127" in str(error)


def test_transposition_errors_preserve_general_value_error_compatibility() -> None:
    assert issubclass(InvalidConcertPitchError, ValueError)
    assert issubclass(InvalidSaxophoneTypeError, ValueError)
    assert issubclass(WrittenPitchOutOfRangeError, ValueError)
