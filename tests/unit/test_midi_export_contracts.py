from __future__ import annotations

from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest

from saxo_ai.domain.midi_export import (
    DEFAULT_MIDI_TEMPO_BPM,
    MIDI_CHANNEL,
    MIDI_EXPORT_POLICY_VERSION,
    MIDI_FILE_TYPE,
    MIDI_PITCH_REPRESENTATION,
    MIDI_TICKS_PER_BEAT,
    InvalidMidiArtifactError,
    InvalidMidiExportSettingsError,
    InvalidMidiPlanError,
    MidiArtifact,
    MidiExportReport,
    MidiExportSettings,
    MidiNotePlan,
)
from saxo_ai.domain.note_confidence import ConfidenceAnnotatedNoteEvent
from saxo_ai.domain.note_events import NoteEvent
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent

ROOT = Path(__file__).resolve().parents[2]


def written_event(*, pitch: int = 60, velocity: int = 100) -> WrittenPitchNoteEvent:
    note = NoteEvent(
        pitch_concert_midi=pitch,
        onset_seconds=0.0,
        offset_seconds=0.5,
        velocity=velocity,
        confidence=0.8,
    )
    annotation = ConfidenceAnnotatedNoteEvent(event=note, is_low_confidence=False)
    return WrittenPitchNoteEvent(source=annotation, written_pitch_midi=pitch + 9)


def test_midi_export_constants_are_stable() -> None:
    assert MIDI_EXPORT_POLICY_VERSION == "1.0"
    assert MIDI_FILE_TYPE == 1
    assert MIDI_TICKS_PER_BEAT == 480
    assert MIDI_CHANNEL == 0
    assert MIDI_PITCH_REPRESENTATION == "concert"
    assert DEFAULT_MIDI_TEMPO_BPM == 120.0


def test_default_settings_are_normalized_and_representable() -> None:
    settings = MidiExportSettings()

    assert settings.tempo_bpm == 120.0
    assert settings.policy_version == "1.0"
    assert settings.tempo_microseconds_per_beat == 500_000


@pytest.mark.parametrize("tempo", [60, 90.5, 120, 240])
def test_valid_tempos_normalize_to_float(tempo: float) -> None:
    settings = MidiExportSettings(tempo_bpm=tempo)

    assert settings.tempo_bpm == float(tempo)
    assert 1 <= settings.tempo_microseconds_per_beat <= 16_777_215


@pytest.mark.parametrize(
    "tempo",
    [0, -1, float("nan"), float("inf"), float("-inf"), True, False, "120", None],
)
def test_invalid_tempos_are_rejected(tempo: object) -> None:
    with pytest.raises(InvalidMidiExportSettingsError):
        MidiExportSettings(tempo_bpm=cast(Any, tempo))


@pytest.mark.parametrize("tempo", [1.0, 200_000_000.0])
def test_unrepresentable_midi_tempos_are_rejected(tempo: float) -> None:
    with pytest.raises(InvalidMidiExportSettingsError):
        MidiExportSettings(tempo_bpm=tempo)


def test_settings_reject_unsupported_policy_version() -> None:
    with pytest.raises(InvalidMidiExportSettingsError):
        MidiExportSettings(policy_version="2.0")


def test_settings_are_immutable() -> None:
    settings = MidiExportSettings()

    with pytest.raises(FrozenInstanceError):
        settings.tempo_bpm = 90.0  # type: ignore[misc]


def test_midi_note_plan_preserves_source_and_concert_pitch() -> None:
    source = written_event(pitch=60, velocity=100)
    plan = MidiNotePlan(
        source=source,
        source_index=2,
        pitch_concert_midi=60,
        velocity=100,
        onset_tick=0,
        offset_tick=480,
    )

    assert plan.source is source
    assert plan.source.written_pitch_midi == 69
    assert plan.pitch_concert_midi == 60
    assert plan.source_index == 2


@pytest.mark.parametrize("source_index", [-1, True, False, 1.0, "1"])
def test_midi_note_plan_rejects_invalid_source_index(source_index: object) -> None:
    source = written_event()

    with pytest.raises(InvalidMidiPlanError):
        MidiNotePlan(
            source=source,
            source_index=cast(Any, source_index),
            pitch_concert_midi=60,
            velocity=100,
            onset_tick=0,
            offset_tick=480,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pitch_concert_midi", 61),
        ("velocity", 0),
        ("velocity", 128),
        ("velocity", True),
        ("onset_tick", -1),
        ("onset_tick", 0.0),
        ("offset_tick", 0),
        ("offset_tick", -1),
        ("offset_tick", 480.0),
    ],
)
def test_midi_note_plan_rejects_invalid_values(field: str, value: object) -> None:
    source = written_event()
    values: dict[str, object] = {
        "source": source,
        "source_index": 0,
        "pitch_concert_midi": 60,
        "velocity": 100,
        "onset_tick": 0,
        "offset_tick": 480,
    }
    values[field] = value

    with pytest.raises(InvalidMidiPlanError):
        MidiNotePlan(**cast(Any, values))


def test_midi_note_plan_rejects_non_written_source() -> None:
    with pytest.raises(InvalidMidiPlanError):
        MidiNotePlan(
            source=cast(Any, object()),
            source_index=0,
            pitch_concert_midi=60,
            velocity=100,
            onset_tick=0,
            offset_tick=480,
        )


def test_midi_note_plan_is_immutable() -> None:
    plan = MidiNotePlan(written_event(), 0, 60, 100, 0, 480)

    with pytest.raises(FrozenInstanceError):
        plan.offset_tick = 481  # type: ignore[misc]


def test_midi_export_report_enforces_counts() -> None:
    settings = MidiExportSettings()
    report = MidiExportReport(
        settings=settings,
        input_event_count=2,
        exported_note_count=2,
        minimum_tick_adjustment_count=1,
        zero_velocity_adjustment_count=1,
        midi_message_count=9,
    )

    assert report.settings is settings

    with pytest.raises(InvalidMidiPlanError):
        MidiExportReport(
            settings=settings,
            input_event_count=1,
            exported_note_count=2,
            minimum_tick_adjustment_count=0,
            zero_velocity_adjustment_count=0,
            midi_message_count=9,
        )


def test_midi_artifact_validates_content_size_and_digest() -> None:
    content = b"MThd" + b"\x00" * 20
    digest = sha256(content).hexdigest()
    artifact = MidiArtifact(
        content=content,
        media_type="audio/midi",
        file_extension=".mid",
        size_bytes=len(content),
        sha256=digest,
    )

    assert artifact.content is content
    assert artifact.size_bytes == len(content)
    assert artifact.sha256 == digest


@pytest.mark.parametrize(
    "changes",
    [
        {"content": "not bytes"},
        {"content": b""},
        {"content": b"not-midi"},
        {"media_type": "application/octet-stream"},
        {"file_extension": ".midi"},
        {"size_bytes": 1},
        {"sha256": "0" * 64},
        {"sha256": "ABC"},
    ],
)
def test_midi_artifact_rejects_inconsistent_values(changes: dict[str, object]) -> None:
    content = b"MThd" + b"\x00" * 20
    values: dict[str, object] = {
        "content": content,
        "media_type": "audio/midi",
        "file_extension": ".mid",
        "size_bytes": len(content),
        "sha256": sha256(content).hexdigest(),
    }
    values.update(changes)

    with pytest.raises(InvalidMidiArtifactError):
        MidiArtifact(**cast(Any, values))


def test_midi_modules_respect_dependency_boundaries() -> None:
    domain = (ROOT / "src/saxo_ai/domain/midi_export.py").read_text()
    application = (ROOT / "src/saxo_ai/application/midi_export.py").read_text()
    infrastructure = (ROOT / "src/saxo_ai/infrastructure/mido_midi.py").read_text()

    assert "import mido" not in domain
    assert "from mido" not in domain
    assert "import mido" not in application
    assert "from mido" not in application
    assert "mido" in infrastructure
    assert "fastapi" not in domain.lower()
    assert "fastapi" not in application.lower()


def test_project_declares_pinned_mido_and_midi_marker() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert '"mido==1.3.3"' in pyproject
    assert "midi_integration" in pyproject
    for forbidden in ("python-rtmidi", "pygame", "fluidsynth", "pretty_midi", "music21"):
        assert forbidden not in pyproject
