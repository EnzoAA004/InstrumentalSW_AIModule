from __future__ import annotations

import hashlib
import os
import shutil
from datetime import UTC, datetime
from importlib.util import find_spec
from uuid import UUID

import pytest
from tests.synthetic_audio import synthetic_saxophone_phrase_wav

from saxo_ai.application.monophonic_processor import (
    MonophonicProcessingDiagnostics,
    MonophonicTranscriptionProcessor,
)
from saxo_ai.application.revision_artifacts import RegisterRevisionArtifacts
from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.domain.models import InputMode, JobStatus, SaxophoneType, TranscriptionJob
from saxo_ai.infrastructure.ffmpeg import FfmpegCanonicalAudioConverter
from saxo_ai.infrastructure.hf_saxophone import (
    BaselineExecutionDiagnostics,
    HfSaxophoneTranscriptionEngine,
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
from saxo_ai.infrastructure.verovio_musicxml import VerovioMusicXmlReader
from saxo_ai.infrastructure.verovio_svg import VerovioSvgScoreRenderer

pytestmark = [pytest.mark.integration, pytest.mark.baseline_integration]

JOB_ID = UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime(2026, 9, 27, 18, 30, tzinfo=UTC)


def _require_runtime() -> None:
    if shutil.which("ffmpeg") is None:
        if os.getenv("SAXO_REQUIRE_FFMPEG") == "1":
            pytest.fail("SAXO_REQUIRE_FFMPEG=1 but ffmpeg is not installed")
        pytest.skip("ffmpeg is not installed")
    if find_spec("hf_midi_transcription") is None:
        reason = "hf-midi-transcription baseline extra is not installed; Python 3.11 CI requires it"
        if os.getenv("SAXO_REQUIRE_BASELINE") == "1":
            pytest.fail(reason)
        pytest.skip(reason)


def test_real_monophonic_pipeline_creates_review_and_downloadable_artifacts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _require_runtime()
    source = synthetic_saxophone_phrase_wav()
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    revisions = InMemoryTranscriptionRevisionRepository()
    registrations = InMemoryTranscriptionReviewRegistrationRepository(reviews, revisions)
    artifacts = InMemoryRevisionArtifactRepository()
    job = TranscriptionJob(
        job_id=JOB_ID,
        status=JobStatus.PROCESSING,
        filename="synthetic-sax.wav",
        size_bytes=len(source),
        audio_sha256=hashlib.sha256(source).hexdigest(),
        saxophone_type=SaxophoneType.ALTO,
        input_mode=InputMode.SOLO,
    )
    jobs.save(job)

    baseline_diagnostics: list[BaselineExecutionDiagnostics] = []
    processor_diagnostics: list[MonophonicProcessingDiagnostics] = []
    processor = MonophonicTranscriptionProcessor(
        canonical_converter=FfmpegCanonicalAudioConverter(),
        transcription_engine=HfSaxophoneTranscriptionEngine(
            diagnostics_observer=baseline_diagnostics.append
        ),
        tempo_estimator=OnsetIntervalTempoEstimator(),
        midi_encoder=MidoMidiFileEncoder(),
        musicxml_encoder=StandardLibraryMusicXmlEncoder(),
        musicxml_reader=VerovioMusicXmlReader(),
        score_renderer=VerovioSvgScoreRenderer(),
        register_review=RegisterTranscriptionReview(
            jobs,
            registrations,
            clock=lambda: NOW,
        ),
        register_artifacts=RegisterRevisionArtifacts(jobs, revisions, artifacts),
        diagnostics_observer=processor_diagnostics.append,
    )

    processor.process(job, source)

    review = reviews.get(JOB_ID)
    revision = revisions.get(JOB_ID, 0)
    bundle = artifacts.get_bundle(JOB_ID, 0)
    assert processor_diagnostics, "processor diagnostics were not emitted"
    diagnostic = processor_diagnostics[0]
    baseline_event_count = baseline_diagnostics[0].event_count if baseline_diagnostics else -1
    with capsys.disabled():
        print(
            "MONOPHONIC_E2E_DIAGNOSTICS "
            f"canonical_audio_bytes={diagnostic.canonical_audio_bytes} "
            f"baseline_events={baseline_event_count} "
            f"raw_events={diagnostic.raw_event_count} "
            f"postprocessed_events={diagnostic.postprocessed_event_count} "
            f"confidence_events={diagnostic.confidence_event_count} "
            f"written_events={diagnostic.written_event_count} "
            f"tempo_bpm={diagnostic.tempo_bpm:.6f} "
            f"quantized_notes={diagnostic.quantized_note_count} "
            f"quantized_items={diagnostic.quantized_timeline_item_count} "
            f"midi_bytes={diagnostic.midi_bytes} "
            f"musicxml_bytes={diagnostic.musicxml_bytes} "
            f"svg_pages={diagnostic.svg_page_count}"
        )

    assert review is not None
    assert review.events, f"no useful review events after diagnostics: {diagnostic}"
    assert revision is not None
    assert bundle is not None
    artifact_ids = {artifact.descriptor.artifact_id for artifact in bundle.artifacts}
    assert {"midi", "musicxml"}.issubset(artifact_ids)
    assert any(artifact_id.startswith("svg-page-") for artifact_id in artifact_ids)

    midi = artifacts.get_artifact(JOB_ID, 0, "midi")
    musicxml = artifacts.get_artifact(JOB_ID, 0, "musicxml")
    assert midi is not None and midi.content.startswith(b"MThd")
    assert musicxml is not None and b"<score-partwise" in musicxml.content
