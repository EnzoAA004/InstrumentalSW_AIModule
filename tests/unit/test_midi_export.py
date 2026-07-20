from __future__ import annotations

from typing import Any, cast

import pytest

from saxo_ai.application.midi_export import (
    ExportWrittenPitchToMidi,
    MidiEncodingError,
    MidiFileEncoder,
    seconds_to_midi_tick,
)
from saxo_ai.domain.midi_export import (
    InvalidMidiArtifactError,
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
from saxo_ai.domain.written_pitch import WrittenPitchNoteEvent, WrittenPitchTranscriptionResult


def written_result(
    specs: tuple[tuple[int, float, float, int, float, bool], ...],
) -> WrittenPitchTranscriptionResult:
    notes = tuple(
        NoteEvent(
            pitch_concert_midi=pitch,
            onset_seconds=onset,
            offset_seconds=offset,
            velocity=velocity,
            confidence=confidence,
        )
        for pitch, onset, offset, velocity, confidence, _ in specs
    )
    batch = NoteEventBatch(events=notes)
    raw = TranscriptionResult(
        notes=batch,
        model=TranscriptionModelIdentity(
            engine_name="filosax",
            engine_version="0.1.1",
            engine_source_revision="a" * 40,
            model_id="xavriley/midi-transcription-models",
            model_revision="b" * 40,
            checkpoint_filename="filosax_25k.pth",
            checkpoint_sha256="c" * 64,
        ),
        settings=TranscriptionSettings(
            sample_rate_hz=16_000,
            device="cpu",
            onset_threshold=0.3,
            offset_threshold=0.3,
            frame_threshold=0.1,
            confidence_method="max_reg_onset_activation_pm2_frames",
        ),
    )
    processed = PostProcessedTranscriptionResult(
        original=raw,
        notes=batch,
        report=NoteEventPostProcessingReport(
            settings=NoteEventPostProcessingSettings(),
            input_event_count=len(notes),
            output_event_count=len(notes),
            short_duration_removed_count=0,
            duplicate_removed_count=0,
            duplicate_group_count=0,
        ),
    )
    annotations = tuple(
        ConfidenceAnnotatedNoteEvent(event=note, is_low_confidence=spec[-1])
        for note, spec in zip(notes, specs, strict=True)
    )
    low_count = sum(1 for spec in specs if spec[-1])
    annotated = ConfidenceAnnotatedTranscriptionResult(
        original=processed,
        annotated_events=annotations,
        report=LowConfidenceReport(
            settings=LowConfidenceSettings(),
            input_event_count=len(notes),
            low_confidence_count=low_count,
            regular_confidence_count=len(notes) - low_count,
        ),
    )
    written = tuple(
        WrittenPitchNoteEvent(
            source=annotation,
            written_pitch_midi=annotation.event.pitch_concert_midi + 9,
        )
        for annotation in annotations
    )
    return WrittenPitchTranscriptionResult(
        original=annotated,
        saxophone_type=SaxophoneType.ALTO,
        events=written,
    )


class RecordingEncoder:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[MidiNotePlan, ...], MidiExportSettings]] = []

    def encode(
        self,
        *,
        plan: tuple[MidiNotePlan, ...],
        settings: MidiExportSettings,
    ) -> bytes:
        self.calls.append((plan, settings))
        body = repr(
            (
                settings.tempo_microseconds_per_beat,
                tuple(
                    (
                        item.source_index,
                        item.pitch_concert_midi,
                        item.velocity,
                        item.onset_tick,
                        item.offset_tick,
                    )
                    for item in plan
                ),
            )
        ).encode()
        return b"MThd" + body


class RaisingEncoder:
    def encode(
        self,
        *,
        plan: tuple[MidiNotePlan, ...],
        settings: MidiExportSettings,
    ) -> bytes:
        raise RuntimeError("external failure")


class InvalidEncoder:
    def __init__(self, value: object) -> None:
        self.value = value

    def encode(
        self,
        *,
        plan: tuple[MidiNotePlan, ...],
        settings: MidiExportSettings,
    ) -> bytes:
        return cast(Any, self.value)


def test_encoder_protocol_is_structural() -> None:
    assert isinstance(RecordingEncoder(), MidiFileEncoder)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0.0, 0), (0.5, 480), (1.0, 960)],
)
def test_seconds_to_ticks_at_120_bpm(seconds: float, expected: int) -> None:
    assert seconds_to_midi_tick(seconds, MidiExportSettings()) == expected


def test_use_case_exports_concert_pitch_not_written_pitch() -> None:
    original = written_result(((60, 0.0, 0.5, 100, 0.8, False),))
    encoder = RecordingEncoder()

    result = ExportWrittenPitchToMidi(encoder).execute(original, MidiExportSettings())

    assert result.original is original
    assert result.plan[0].pitch_concert_midi == 60
    assert result.plan[0].source.written_pitch_midi == 69
    assert b"60" in result.artifact.content
    assert result.report.exported_note_count == 1


def test_short_positive_duration_gets_one_tick_and_is_reported() -> None:
    original = written_result(((60, 0.0, 0.0001, 100, 0.8, False),))

    result = ExportWrittenPitchToMidi(RecordingEncoder()).execute(original, MidiExportSettings())

    assert result.plan[0].onset_tick == 0
    assert result.plan[0].offset_tick == 1
    assert result.report.minimum_tick_adjustment_count == 1
    assert original.events[0].source.event.offset_seconds == 0.0001


@pytest.mark.parametrize(
    ("source_velocity", "expected_velocity", "expected_adjustments"),
    [(0, 1, 1), (1, 1, 0), (127, 127, 0)],
)
def test_velocity_zero_is_adapted_without_mutating_source(
    source_velocity: int,
    expected_velocity: int,
    expected_adjustments: int,
) -> None:
    original = written_result(((60, 0.0, 0.5, source_velocity, 0.8, False),))

    result = ExportWrittenPitchToMidi(RecordingEncoder()).execute(original, MidiExportSettings())

    assert result.plan[0].velocity == expected_velocity
    assert result.report.zero_velocity_adjustment_count == expected_adjustments
    assert original.events[0].source.event.velocity == source_velocity


def test_plan_is_sorted_deterministically_without_reordering_original() -> None:
    original = written_result(
        (
            (72, 1.0, 1.5, 100, 0.8, False),
            (67, 0.0, 0.5, 100, 0.7, True),
            (60, 0.0, 0.25, 100, 0.9, False),
            (65, 0.0, 0.25, 100, 0.6, False),
        )
    )

    result = ExportWrittenPitchToMidi(RecordingEncoder()).execute(original, MidiExportSettings())

    assert [event.source.event.pitch_concert_midi for event in original.events] == [72, 67, 60, 65]
    assert [item.pitch_concert_midi for item in result.plan] == [60, 65, 67, 72]
    assert [item.source_index for item in result.plan] == [2, 3, 1, 0]
    assert result.plan == tuple(
        sorted(
            result.plan,
            key=lambda item: (
                item.onset_tick,
                item.offset_tick,
                item.pitch_concert_midi,
                item.source_index,
            ),
        )
    )


def test_empty_result_produces_nonempty_artifact_and_zero_note_report() -> None:
    original = written_result(())

    result = ExportWrittenPitchToMidi(RecordingEncoder()).execute(original, MidiExportSettings())

    assert result.plan == ()
    assert result.artifact.content.startswith(b"MThd")
    assert result.artifact.content
    assert result.report.input_event_count == 0
    assert result.report.exported_note_count == 0
    assert result.report.midi_message_count == 6


def test_complete_provenance_chain_is_preserved() -> None:
    original = written_result(((60, 0.0, 0.5, 100, 0.4, True),))

    result = ExportWrittenPitchToMidi(RecordingEncoder()).execute(original, MidiExportSettings())

    assert result.original is original
    assert result.plan[0].source is original.events[0]
    assert result.plan[0].source.source is original.original.annotated_events[0]
    assert result.plan[0].source.source.event is original.original.original.notes.events[0]
    assert result.original.original.original.original.model.engine_source_revision == "a" * 40
    assert result.original.original.original.original.model.model_revision == "b" * 40
    assert result.original.original.original.original.model.checkpoint_filename == "filosax_25k.pth"
    assert result.original.original.original.report is original.original.original.report
    assert result.original.original.report is original.original.report
    assert result.plan[0].source.source.event.confidence == 0.4
    assert result.plan[0].source.source.is_low_confidence is True
    assert result.original.saxophone_type is SaxophoneType.ALTO


def test_same_input_and_settings_are_deterministic() -> None:
    original = written_result(((60, 0.0, 0.5, 100, 0.8, False),))
    use_case = ExportWrittenPitchToMidi(RecordingEncoder())

    first = use_case.execute(original, MidiExportSettings())
    second = use_case.execute(original, MidiExportSettings())

    assert first.artifact.content == second.artifact.content
    assert first.artifact.sha256 == second.artifact.sha256
    assert first.plan == second.plan


def test_different_tempo_changes_ticks_and_artifact_but_not_sources() -> None:
    original = written_result(((60, 0.0, 0.5, 100, 0.8, False),))
    use_case = ExportWrittenPitchToMidi(RecordingEncoder())

    slow = use_case.execute(original, MidiExportSettings(tempo_bpm=60))
    fast = use_case.execute(original, MidiExportSettings(tempo_bpm=120))

    assert slow.plan[0].pitch_concert_midi == fast.plan[0].pitch_concert_midi == 60
    assert slow.plan[0].source is fast.plan[0].source is original.events[0]
    assert slow.plan[0].offset_tick == 240
    assert fast.plan[0].offset_tick == 480
    assert slow.artifact.sha256 != fast.artifact.sha256


def test_encoder_failure_is_wrapped_with_controlled_error() -> None:
    original = written_result(())

    with pytest.raises(MidiEncodingError) as captured:
        ExportWrittenPitchToMidi(RaisingEncoder()).execute(original, MidiExportSettings())

    assert isinstance(captured.value.__cause__, RuntimeError)
    assert "external failure" not in str(captured.value)


@pytest.mark.parametrize("value", ["MThd", b"", b"not-midi"])
def test_invalid_encoder_result_is_controlled(value: object) -> None:
    original = written_result(())

    with pytest.raises(InvalidMidiArtifactError):
        ExportWrittenPitchToMidi(InvalidEncoder(value)).execute(original, MidiExportSettings())


def test_use_case_rejects_invalid_original_and_settings_before_encoder() -> None:
    encoder = RecordingEncoder()

    with pytest.raises(InvalidMidiArtifactError):
        ExportWrittenPitchToMidi(encoder).execute(cast(Any, object()), MidiExportSettings())
    with pytest.raises(InvalidMidiArtifactError):
        ExportWrittenPitchToMidi(encoder).execute(written_result(()), cast(Any, object()))
    assert encoder.calls == []
