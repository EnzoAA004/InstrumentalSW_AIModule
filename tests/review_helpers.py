from uuid import UUID

from saxo_ai.domain.models import InputMode, JobStatus, SaxophoneType, TranscriptionJob
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

JOB_ID = UUID("11111111-1111-1111-1111-111111111111")


def build_job(saxophone_type: SaxophoneType = SaxophoneType.ALTO) -> TranscriptionJob:
    return TranscriptionJob(
        job_id=JOB_ID,
        status=JobStatus.UPLOADED,
        filename="take.wav",
        size_bytes=15,
        audio_sha256="a" * 64,
        saxophone_type=saxophone_type,
        input_mode=InputMode.SOLO,
    )


def build_written_result(
    *,
    saxophone_type: SaxophoneType = SaxophoneType.ALTO,
    threshold: float = 0.5,
    events: tuple[tuple[int, int, float, float, int, float, bool], ...] | None = None,
) -> WrittenPitchTranscriptionResult:
    rows = events if events is not None else (
        (60, 69, 0.0, 0.5, 90, 0.42, True),
        (67, 76, 0.25, 1.0, 100, 0.82, False),
    )
    notes = tuple(
        NoteEvent(
            pitch_concert_midi=concert,
            onset_seconds=onset,
            offset_seconds=offset,
            velocity=velocity,
            confidence=confidence,
        )
        for concert, _written, onset, offset, velocity, confidence, _low in rows
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
            sample_rate_hz=16000,
            device="cpu",
            onset_threshold=0.3,
            offset_threshold=0.3,
            frame_threshold=0.1,
            confidence_method="model_probability",
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
        ConfidenceAnnotatedNoteEvent(event=note, is_low_confidence=row[6])
        for note, row in zip(notes, rows, strict=True)
    )
    low_count = sum(annotation.is_low_confidence for annotation in annotations)
    confidence = ConfidenceAnnotatedTranscriptionResult(
        original=processed,
        annotated_events=annotations,
        report=LowConfidenceReport(
            settings=LowConfidenceSettings(low_confidence_threshold=threshold),
            input_event_count=len(notes),
            low_confidence_count=low_count,
            regular_confidence_count=len(notes) - low_count,
        ),
    )
    return WrittenPitchTranscriptionResult(
        original=confidence,
        saxophone_type=saxophone_type,
        events=tuple(
            WrittenPitchNoteEvent(source=annotation, written_pitch_midi=row[1])
            for annotation, row in zip(annotations, rows, strict=True)
        ),
    )
