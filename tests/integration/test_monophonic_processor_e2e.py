from __future__ import annotations

import hashlib
import io
import math
import os
import shutil
import struct
import wave
from datetime import UTC, datetime
from importlib.util import find_spec
from uuid import UUID

import pytest

from saxo_ai.application.monophonic_processor import MonophonicTranscriptionProcessor
from saxo_ai.application.revision_artifacts import RegisterRevisionArtifacts
from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.domain.models import InputMode, JobStatus, SaxophoneType, TranscriptionJob
from saxo_ai.infrastructure.ffmpeg import FfmpegCanonicalAudioConverter
from saxo_ai.infrastructure.hf_saxophone import HfSaxophoneTranscriptionEngine
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


def _synthetic_saxophone_like_wav() -> bytes:
    sample_rate = 16_000
    duration_seconds = 2.0
    frame_count = int(sample_rate * duration_seconds)
    frames = bytearray()
    for index in range(frame_count):
        time_seconds = index / sample_rate
        fade = min(
            1.0,
            index / (sample_rate * 0.08),
            (frame_count - index) / (sample_rate * 0.08),
        )
        vibrato = 1.0 + 0.003 * math.sin(2.0 * math.pi * 5.2 * time_seconds)
        phase = 2.0 * math.pi * 440.0 * vibrato * time_seconds
        sample = fade * (
            0.70 * math.sin(phase)
            + 0.20 * math.sin(2.0 * phase)
            + 0.10 * math.sin(3.0 * phase)
        )
        integer = max(-32768, min(32767, round(sample * 24000)))
        frames.extend(struct.pack("<h", integer))

    destination = io.BytesIO()
    with wave.open(destination, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    return destination.getvalue()


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


def test_real_monophonic_pipeline_creates_review_and_downloadable_artifacts() -> None:
    _require_runtime()
    source = _synthetic_saxophone_like_wav()
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

    processor = MonophonicTranscriptionProcessor(
        canonical_converter=FfmpegCanonicalAudioConverter(),
        transcription_engine=HfSaxophoneTranscriptionEngine(),
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
    )

    processor.process(job, source)

    review = reviews.get(JOB_ID)
    revision = revisions.get(JOB_ID, 0)
    bundle = artifacts.get_bundle(JOB_ID, 0)
    assert review is not None
    assert review.events
    assert revision is not None
    assert bundle is not None
    artifact_ids = {artifact.descriptor.artifact_id for artifact in bundle.artifacts}
    assert {"midi", "musicxml"}.issubset(artifact_ids)
    assert any(artifact_id.startswith("svg-page-") for artifact_id in artifact_ids)

    midi = artifacts.get_artifact(JOB_ID, 0, "midi")
    musicxml = artifacts.get_artifact(JOB_ID, 0, "musicxml")
    assert midi is not None and midi.content.startswith(b"MThd")
    assert musicxml is not None and b"<score-partwise" in musicxml.content
