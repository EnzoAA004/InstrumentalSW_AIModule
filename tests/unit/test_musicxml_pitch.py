from __future__ import annotations

import pytest

from saxo_ai.application.musicxml_export import musicxml_pitch_for_midi


@pytest.mark.parametrize(
    ("midi", "step", "alter", "octave"),
    [
        (60, "C", 0, 4),
        (61, "D", -1, 4),
        (62, "D", 0, 4),
        (63, "E", -1, 4),
        (64, "E", 0, 4),
        (65, "F", 0, 4),
        (66, "G", -1, 4),
        (67, "G", 0, 4),
        (68, "A", -1, 4),
        (69, "A", 0, 4),
        (70, "B", -1, 4),
        (71, "B", 0, 4),
    ],
)
def test_all_pitch_classes_prefer_flats(
    midi: int,
    step: str,
    alter: int,
    octave: int,
) -> None:
    pitch = musicxml_pitch_for_midi(midi)
    assert (pitch.step, pitch.alter, pitch.octave) == (step, alter, octave)


@pytest.mark.parametrize(
    ("midi", "expected"),
    [
        (0, ("C", 0, -1)),
        (60, ("C", 0, 4)),
        (61, ("D", -1, 4)),
        (69, ("A", 0, 4)),
        (127, ("G", 0, 9)),
    ],
)
def test_pitch_boundaries_and_examples(midi: int, expected: tuple[str, int, int]) -> None:
    pitch = musicxml_pitch_for_midi(midi)
    assert (pitch.step, pitch.alter, pitch.octave) == expected


@pytest.mark.parametrize("value", [-1, 128, True, False, 60.0, "60", None])
def test_pitch_spelling_rejects_non_midi_values(value: object) -> None:
    with pytest.raises(ValueError):
        musicxml_pitch_for_midi(value)
