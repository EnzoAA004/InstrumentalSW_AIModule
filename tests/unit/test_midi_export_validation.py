from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast

import mido  # type: ignore[import-untyped]
import pytest

from saxo_ai.application.midi_export import (
    ExportWrittenPitchToMidi,
    MidiEncodingError,
    seconds_to_midi_tick,
)
from saxo_ai.domain.midi_export import (
    InvalidMidiArtifactError,
    InvalidMidiExportSettingsError,
    InvalidMidiPlanError,
    MidiArtifact,
    MidiExportReport,
    MidiExportResult,
    MidiExportSettings,
    MidiNotePlan,
)
from saxo_ai.domain.models import SaxophoneType
from saxo_ai.domain.note_confidence import (
    ConfidenceAnnotatedNoteEvent,
    ConfidenceAnnotatedTranscriptionResult,
    LowConfidenceReport,
    LowConfidenceSettings,
)
from saxo_ai.domain.note_event_postprocessing import (
    NoteEventPostProcessingReport,
    NoteEventPostProcessingSettings,
    PostProcessedTranscriptionResult,
)
from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.domain.written_pitch import (
    WrittenPitchNoteEvent,
    WrittenPitchTranscriptionResult,
)
from saxo_ai.infrastructure import mido_midi
from saxo_ai.infrastructure.mido_midi import MidoMidiFileEncoder


def written_result(
    specs: tuple[tuple[int, float, float, int], ...] = (),
) -> WrittenPitchTranscriptionResult:
    notes = tuple(
        NoteEvent(pitch, onset, offset, velocity, 0.8)
        for pitch, onset, offset, velocity in specs
    )
    batch = NoteEventBatch(notes)
    raw = TranscriptionResult(
        batch,
        TranscriptionModelIdentity(
            "filosax",
            "0.1.1",
            "a" * 40,
            "model",
            "b" * 40,
            "filosax_25k.pth",
            "c" * 64,
        ),
        TranscriptionSettings(16_000, "cpu", 0.3, 0.3, 0.1, "activation"),
    )
    processed = PostProcessedTranscriptionResult(
        raw,
        batch,
        NoteEventPostProcessingReport(
            NoteEventPostProcessingSettings(), len(notes), len(notes), 0, 0, 0
        ),
    )
    annotations = tuple(ConfidenceAnnotatedNoteEvent(note, False) for note in notes)
    annotated = ConfidenceAnnotatedTranscriptionResult(
        processed,
        annotations,
        LowConfidenceReport(LowConfidenceSettings(), len(notes), 0, len(notes)),
    )
    return WrittenPitchTranscriptionResult(
        annotated,
        SaxophoneType.ALTO,
        tuple(
            WrittenPitchNoteEvent(annotation, annotation.event.pitch_concert_midi + 9)
            for annotation in annotations
        ),
    )


def valid_artifact() -> MidiArtifact:
    content = b"MThd" + b"\x00" * 20
    return MidiArtifact(
        content,
        "audio/midi",
        ".mid",
        len(content),
        sha256(content).hexdigest(),
    )


@pytest.mark.parametrize("seconds", [True, False, "0", None])
def test_seconds_to_tick_rejects_non_numeric_values(seconds: object) -> None:
    with pytest.raises(InvalidMidiPlanError):
        seconds_to_midi_tick(cast(Any, seconds), MidiExportSettings())


@pytest.mark.parametrize("seconds", [-1.0, float("nan"), float("inf"), float("-inf")])
def test_seconds_to_tick_rejects_invalid_numeric_values(seconds: float) -> None:
    with pytest.raises(InvalidMidiPlanError):
        seconds_to_midi_tick(seconds, MidiExportSettings())


def test_seconds_to_tick_rejects_invalid_settings() -> None:
    with pytest.raises(InvalidMidiExportSettingsError):
        seconds_to_midi_tick(0.0, cast(Any, object()))


def test_use_case_rejects_non_encoder_dependency() -> None:
    with pytest.raises(TypeError):
        ExportWrittenPitchToMidi(cast(Any, object()))


class ControlledFailureEncoder:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def encode(
        self,
        *,
        plan: tuple[MidiNotePlan, ...],
        settings: MidiExportSettings,
    ) -> bytes:
        raise self.error


@pytest.mark.parametrize(
    "error",
    [MidiEncodingError("controlled"), InvalidMidiArtifactError("controlled")],
)
def test_controlled_encoder_failures_are_preserved(error: Exception) -> None:
    with pytest.raises(type(error)) as captured:
        ExportWrittenPitchToMidi(ControlledFailureEncoder(error)).execute(
            written_result(), MidiExportSettings()
        )
    assert captured.value is error


@pytest.mark.parametrize("pitch", [True, 60.0, "60"])
def test_midi_note_plan_rejects_non_integer_concert_pitch(pitch: object) -> None:
    source = written_result(((60, 0.0, 0.5, 100),)).events[0]
    with pytest.raises(InvalidMidiPlanError):
        MidiNotePlan(
            source=source,
            source_index=0,
            pitch_concert_midi=cast(Any, pitch),
            velocity=100,
            onset_tick=0,
            offset_tick=480,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"settings": object()},
        {"input_event_count": -1},
        {"minimum_tick_adjustment_count": 2},
        {"zero_velocity_adjustment_count": 2},
        {"midi_message_count": 6},
    ],
)
def test_midi_export_report_rejects_invalid_invariants(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "settings": MidiExportSettings(),
        "input_event_count": 1,
        "exported_note_count": 1,
        "minimum_tick_adjustment_count": 0,
        "zero_velocity_adjustment_count": 0,
        "midi_message_count": 7,
    }
    values.update(changes)
    with pytest.raises(InvalidMidiPlanError):
        MidiExportReport(**cast(Any, values))


def test_midi_export_result_accepts_empty_complete_contract() -> None:
    original = written_result()
    report = MidiExportReport(MidiExportSettings(), 0, 0, 0, 0, 5)
    result = MidiExportResult(original, (), valid_artifact(), report)
    assert result.original is original


@pytest.mark.parametrize(
    "field_value",
    [
        ("original", object()),
        ("plan", []),
        ("artifact", object()),
        ("report", object()),
    ],
)
def test_midi_export_result_rejects_invalid_top_level_contract(
    field_value: tuple[str, object],
) -> None:
    values: dict[str, object] = {
        "original": written_result(),
        "plan": (),
        "artifact": valid_artifact(),
        "report": MidiExportReport(MidiExportSettings(), 0, 0, 0, 0, 5),
    }
    values[field_value[0]] = field_value[1]
    with pytest.raises((InvalidMidiPlanError, InvalidMidiArtifactError)):
        MidiExportResult(**cast(Any, values))


def message(message_type: str, *, time: object = 0, **values: object) -> Any:
    return SimpleNamespace(type=message_type, time=time, **values)


def valid_parsed_midi() -> Any:
    metadata = [
        message("track_name", name="Saxo Metadata"),
        message("set_tempo", tempo=500_000),
        message("end_of_track"),
    ]
    notes = [
        message("track_name", name="Saxo Concert Pitch"),
        message("end_of_track"),
    ]
    return SimpleNamespace(type=1, ticks_per_beat=480, tracks=[metadata, notes])


@pytest.mark.parametrize(
    "mutation",
    [
        "type",
        "division",
        "tracks",
        "metadata_order",
        "metadata_name",
        "tempo",
        "note_missing",
        "note_name",
        "note_end",
        "message_mismatch",
    ],
)
def test_external_parser_validation_rejects_structural_mismatch(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed = valid_parsed_midi()
    if mutation == "type":
        parsed.type = 0
    elif mutation == "division":
        parsed.ticks_per_beat = 96
    elif mutation == "tracks":
        parsed.tracks = parsed.tracks[:1]
    elif mutation == "metadata_order":
        parsed.tracks[0][1].type = "time_signature"
    elif mutation == "metadata_name":
        parsed.tracks[0][0].name = "Wrong"
    elif mutation == "tempo":
        parsed.tracks[0][1].tempo = 400_000
    elif mutation == "note_missing":
        parsed.tracks[1] = []
    elif mutation == "note_name":
        parsed.tracks[1][0].name = "Wrong"
    elif mutation == "note_end":
        parsed.tracks[1][-1].type = "marker"
    elif mutation == "message_mismatch":
        parsed.tracks[1].insert(
            1,
            message("note_on", note=60, velocity=100, channel=0),
        )
    monkeypatch.setattr(mido, "MidiFile", lambda **kwargs: parsed)

    with pytest.raises(InvalidMidiArtifactError):
        mido_midi._validate_encoded_content(
            b"MThd", plan=(), settings=MidiExportSettings()
        )


@pytest.mark.parametrize(
    "parsed_message",
    [
        message("note_on", time=-1, note=60, velocity=100, channel=0),
        message("note_on", time=0.5, note=60, velocity=100, channel=0),
        message("note_on", time=0, note=128, velocity=100, channel=0),
        message("note_on", time=0, note=60, velocity=128, channel=0),
    ],
)
def test_parsed_note_message_validation_rejects_invalid_data(
    parsed_message: Any,
) -> None:
    with pytest.raises(InvalidMidiArtifactError):
        mido_midi._parsed_note_messages([parsed_message])


def test_external_parser_validation_wraps_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**kwargs: object) -> object:
        raise ValueError("bad file")

    monkeypatch.setattr(mido, "MidiFile", fail)
    with pytest.raises(InvalidMidiArtifactError) as captured:
        mido_midi._validate_encoded_content(
            b"not midi", plan=(), settings=MidiExportSettings()
        )
    assert isinstance(captured.value.__cause__, ValueError)


def test_mido_encoder_wraps_unexpected_external_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise RuntimeError("external mido failure")

    monkeypatch.setattr(mido, "MidiFile", fail)
    with pytest.raises(MidiEncodingError) as captured:
        MidoMidiFileEncoder().encode(plan=(), settings=MidiExportSettings())
    assert isinstance(captured.value.__cause__, RuntimeError)
    assert "external mido failure" not in str(captured.value)
