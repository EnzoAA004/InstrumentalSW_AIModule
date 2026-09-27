from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

import pytest
from tests.score_render_helpers import ParsingMusicXmlReader

from saxo_ai.application.errors import AudioContentInvalidError
from saxo_ai.application.monophonic_processor import MonophonicTranscriptionProcessor
from saxo_ai.application.processing import TerminalProcessingError, TranscriptionWorker
from saxo_ai.application.revision_artifacts import RegisterRevisionArtifacts
from saxo_ai.application.score_rendering import (
    ScoreRendererOutput,
    ScoreRendererPage,
    ScoreRenderingError,
)
from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.domain.audio import (
    CanonicalAudioMetadata,
    CanonicalAudioResult,
    CanonicalAudioSettings,
    OriginalAudioReference,
)
from saxo_ai.domain.midi_export import MidiExportSettings, MidiNotePlan
from saxo_ai.domain.models import (
    InputMode,
    JobFailureCode,
    JobStatus,
    SaxophoneType,
    TranscriptionJob,
)
from saxo_ai.domain.note_events import NoteEvent, NoteEventBatch
from saxo_ai.domain.processing import ProcessingQueueMessage
from saxo_ai.domain.score_rendering import SVG_NAMESPACE, ScoreRenderSettings
from saxo_ai.domain.transcription import (
    TranscriptionModelIdentity,
    TranscriptionResult,
    TranscriptionSettings,
)
from saxo_ai.infrastructure.mido_midi import MidoMidiFileEncoder
from saxo_ai.infrastructure.musicxml_encoder import StandardLibraryMusicXmlEncoder
from saxo_ai.infrastructure.onset_interval_tempo import OnsetIntervalTempoEstimator
from saxo_ai.infrastructure.repositories import (
    InMemoryRevisionArtifactRepository,
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRegistrationRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)

JOB_ID = UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)


def _job() -> TranscriptionJob:
    return TranscriptionJob(
        job_id=JOB_ID,
        status=JobStatus.PROCESSING,
        filename="solo.wav",
        size_bytes=12,
        audio_sha256="a" * 64,
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )


def _transcription(*, one_note: bool = False) -> TranscriptionResult:
    specs = (
        ((60, 0.0, 0.4),)
        if one_note
        else (
            (60, 0.0, 0.4),
            (62, 0.5, 0.9),
            (64, 1.0, 1.4),
        )
    )
    return TranscriptionResult(
        notes=NoteEventBatch(
            events=tuple(
                NoteEvent(
                    pitch_concert_midi=pitch,
                    onset_seconds=onset,
                    offset_seconds=offset,
                    velocity=90,
                    confidence=0.9,
                )
                for pitch, onset, offset in specs
            )
        ),
        model=TranscriptionModelIdentity(
            engine_name="fake-baseline",
            engine_version="1.0",
            engine_source_revision="a" * 40,
            model_id="fake/model",
            model_revision="b" * 40,
            checkpoint_filename="checkpoint.pth",
            checkpoint_sha256="c" * 64,
        ),
        settings=TranscriptionSettings(
            sample_rate_hz=16_000,
            device="cpu",
            onset_threshold=0.3,
            offset_threshold=0.3,
            frame_threshold=0.1,
            confidence_method="model_probability",
        ),
    )


class CopyCanonicalConverter:
    def convert(
        self,
        *,
        source: object,
        destination: object,
        settings: CanonicalAudioSettings,
        original: OriginalAudioReference,
    ) -> CanonicalAudioResult:
        assert hasattr(source, "read")
        assert hasattr(destination, "write")
        raw = source.read(-1)
        destination.write(b"canonical:" + raw)
        return CanonicalAudioResult(
            original=original,
            settings=settings,
            metadata=CanonicalAudioMetadata(
                container="wav",
                codec="pcm_s16le",
                sample_rate_hz=settings.sample_rate_hz,
                channels=settings.channels,
                sample_width_bits=settings.sample_width_bits,
                duration_seconds=1.5,
                tool_name="fake",
                tool_version="1.0",
                preprocessing_schema_version=settings.schema_version,
            ),
        )


class InvalidAudioConverter(CopyCanonicalConverter):
    def convert(
        self,
        *,
        source: object,
        destination: object,
        settings: CanonicalAudioSettings,
        original: OriginalAudioReference,
    ) -> CanonicalAudioResult:
        raise AudioContentInvalidError(return_code=1, stderr="invalid bytes")


class StaticEngine:
    def __init__(self, result: TranscriptionResult) -> None:
        self.result = result
        self.received: bytes | None = None

    def transcribe(self, source: object) -> TranscriptionResult:
        assert hasattr(source, "read")
        self.received = source.read(-1)
        return self.result


class SvgRenderer:
    def render(
        self,
        *,
        content: bytes,
        settings: ScoreRenderSettings,
    ) -> ScoreRendererOutput:
        assert content
        assert settings.scale > 0
        return ScoreRendererOutput(
            pages=(
                ScoreRendererPage(
                    page_number=1,
                    content=(
                        f'<svg xmlns="{SVG_NAMESPACE}" width="100" height="100"></svg>'
                    ).encode(),
                ),
            ),
            logs=(),
        )


class FailingSvgRenderer:
    def render(
        self,
        *,
        content: bytes,
        settings: ScoreRenderSettings,
    ) -> ScoreRendererOutput:
        raise ScoreRenderingError(
            "renderer unavailable",
            stage="render",
            page_number=None,
            logs=(),
        )


class RecordingMidiEncoder:
    def __init__(self) -> None:
        self.settings: MidiExportSettings | None = None

    def encode(
        self,
        *,
        plan: tuple[MidiNotePlan, ...],
        settings: MidiExportSettings,
    ) -> bytes:
        assert plan
        self.settings = settings
        return b"MThd-fallback-test"


def _processor(
    *,
    converter: object | None = None,
    engine: StaticEngine | None = None,
    midi_encoder: object | None = None,
    renderer: object | None = None,
) -> tuple[
    MonophonicTranscriptionProcessor,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
    InMemoryRevisionArtifactRepository,
]:
    jobs = InMemoryTranscriptionJobRepository()
    jobs.save(_job())
    reviews = InMemoryTranscriptionReviewRepository()
    revisions = InMemoryTranscriptionRevisionRepository()
    registrations = InMemoryTranscriptionReviewRegistrationRepository(reviews, revisions)
    artifacts = InMemoryRevisionArtifactRepository()
    processor = MonophonicTranscriptionProcessor(
        canonical_converter=converter or CopyCanonicalConverter(),
        transcription_engine=engine or StaticEngine(_transcription()),
        tempo_estimator=OnsetIntervalTempoEstimator(),
        midi_encoder=midi_encoder or MidoMidiFileEncoder(),
        musicxml_encoder=StandardLibraryMusicXmlEncoder(),
        musicxml_reader=ParsingMusicXmlReader(),
        score_renderer=renderer or SvgRenderer(),
        register_review=RegisterTranscriptionReview(
            jobs,
            registrations,
            clock=lambda: NOW,
        ),
        register_artifacts=RegisterRevisionArtifacts(jobs, revisions, artifacts),
        fallback_tempo_bpm=120.0,
    )
    return processor, reviews, revisions, artifacts


def test_processor_runs_monophonic_pipeline_and_registers_revision_zero_artifacts() -> None:
    engine = StaticEngine(_transcription())
    processor, reviews, revisions, artifacts = _processor(engine=engine)

    processor.process(_job(), b"original-source")

    assert engine.received == b"canonical:original-source"
    review = reviews.get(JOB_ID)
    revision = revisions.get(JOB_ID, 0)
    bundle = artifacts.get_bundle(JOB_ID, 0)
    assert review is not None
    assert revision is not None
    assert bundle is not None
    assert [artifact.descriptor.artifact_id for artifact in bundle.artifacts] == [
        "midi",
        "musicxml",
        "svg-page-001",
    ]
    assert review.saxophone_type is SaxophoneType.ALTO
    assert all(event.written_pitch_midi == event.source.event.pitch_concert_midi + 9 for event in review.events)


def test_processor_uses_manual_fallback_tempo_when_automatic_estimation_is_unavailable() -> None:
    midi_encoder = RecordingMidiEncoder()
    processor, _reviews, _revisions, artifacts = _processor(
        engine=StaticEngine(_transcription(one_note=True)),
        midi_encoder=midi_encoder,
    )

    processor.process(_job(), b"one-note")

    assert midi_encoder.settings is not None
    assert midi_encoder.settings.tempo_bpm == 120.0
    assert artifacts.get_bundle(JOB_ID, 0) is not None


def test_score_render_failure_preserves_midi_and_musicxml_as_completed_artifacts() -> None:
    processor, reviews, revisions, artifacts = _processor(renderer=FailingSvgRenderer())

    processor.process(_job(), b"render-fails")

    assert reviews.get(JOB_ID) is not None
    assert revisions.get(JOB_ID, 0) is not None
    bundle = artifacts.get_bundle(JOB_ID, 0)
    assert bundle is not None
    assert [artifact.descriptor.artifact_id for artifact in bundle.artifacts] == [
        "midi",
        "musicxml",
    ]


def test_invalid_audio_becomes_terminal_processing_error_with_specific_failure_code() -> None:
    processor, reviews, revisions, artifacts = _processor(converter=InvalidAudioConverter())

    with pytest.raises(TerminalProcessingError) as raised:
        processor.process(_job(), b"broken")

    assert raised.value.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert reviews.get(JOB_ID) is None
    assert revisions.get(JOB_ID, 0) is None
    assert artifacts.get_bundle(JOB_ID, 0) is None


class OneMessageQueue:
    def __init__(self) -> None:
        self.message = ProcessingQueueMessage(job_id=JOB_ID, attempt=1)
        self.acked = False
        self.retried = False

    def enqueue(self, job_id: UUID) -> None:
        raise AssertionError("not used")

    def claim(self) -> ProcessingQueueMessage | None:
        message, self.message = self.message, None  # type: ignore[assignment]
        return message

    def ack(self, message: ProcessingQueueMessage) -> bool:
        self.acked = True
        return True

    def retry(self, message: ProcessingQueueMessage) -> bool:
        self.retried = True
        return True


class StaticOriginals:
    def save(self, job_id: UUID, source: object) -> None:
        raise AssertionError("not used")

    def get(self, job_id: UUID) -> bytes | None:
        return b"broken"


class TerminalProcessor:
    def process(self, job: TranscriptionJob, source: bytes) -> None:
        raise TerminalProcessingError(JobFailureCode.AUDIO_CONTENT_INVALID)


def test_worker_does_not_retry_terminal_processor_failures() -> None:
    jobs = InMemoryTranscriptionJobRepository()
    jobs.save(_job())
    queue = OneMessageQueue()
    worker = TranscriptionWorker(
        jobs=jobs,
        originals=StaticOriginals(),
        queue=queue,
        processor=TerminalProcessor(),
        max_attempts=3,
    )

    assert worker.run_once() is True

    failed = jobs.get(JOB_ID)
    assert failed is not None
    assert failed.status is JobStatus.FAILED
    assert failed.failure_code is JobFailureCode.AUDIO_CONTENT_INVALID
    assert queue.acked is True
    assert queue.retried is False
