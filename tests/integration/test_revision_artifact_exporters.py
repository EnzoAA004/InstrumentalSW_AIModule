from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

import pytest
from tests.review_helpers import build_job
from tests.score_render_helpers import long_musicxml_result, midi_result

from saxo_ai.application.revision_artifacts import RegisterRevisionArtifacts
from saxo_ai.application.score_rendering import RenderMusicXmlToSvg
from saxo_ai.domain.revision_artifacts import (
    ArtifactType,
    RevisionArtifact,
    RevisionArtifactBundle,
    RevisionArtifactDescriptor,
)
from saxo_ai.domain.score_rendering import ScoreRenderSettings
from saxo_ai.domain.transcription_revisions import DerivedArtifactsStatus, TranscriptionRevision
from saxo_ai.infrastructure.repositories import (
    InMemoryRevisionArtifactRepository,
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionRevisionRepository,
)
from saxo_ai.infrastructure.verovio_svg import VerovioSvgScoreRenderer

pytestmark = [pytest.mark.integration, pytest.mark.score_render_integration]

JOB_ID = UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def descriptor(
    *,
    artifact_id: str,
    artifact_type: ArtifactType,
    filename: str,
    media_type: str,
    extension: str,
    content: bytes,
    order: int,
) -> RevisionArtifact:
    metadata = RevisionArtifactDescriptor(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        filename=filename,
        media_type=media_type,
        extension=extension,
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
        order=order,
    )
    return RevisionArtifact(metadata, content)


def existing_repositories() -> tuple[
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionRevisionRepository,
]:
    job = build_job()
    jobs = InMemoryTranscriptionJobRepository()
    jobs.save(job)
    revisions = InMemoryTranscriptionRevisionRepository()
    revision_zero = TranscriptionRevision(
        job_id=JOB_ID,
        revision_number=0,
        parent_revision_number=None,
        created_at=NOW,
        saxophone_type=job.saxophone_type,
        events=(),
        derived_artifacts_status=DerivedArtifactsStatus.CURRENT,
    )
    revisions.initialize(JOB_ID, revision_zero)
    for revision_number in range(1, 8):
        revision = TranscriptionRevision(
            job_id=JOB_ID,
            revision_number=revision_number,
            parent_revision_number=revision_number - 1,
            created_at=NOW,
            saxophone_type=job.saxophone_type,
            events=(),
            derived_artifacts_status=DerivedArtifactsStatus.CURRENT,
        )
        revisions.append(JOB_ID, revision_number - 1, revision)
    return jobs, revisions


def test_real_exporters_register_midi_musicxml_and_multiple_svg_pages() -> None:
    musicxml = long_musicxml_result(note_count=96, revision=7)
    midi = midi_result(musicxml)
    rendered = RenderMusicXmlToSvg(VerovioSvgScoreRenderer()).execute(
        musicxml,
        ScoreRenderSettings(page_width=900, page_height=600, scale=100),
    )
    assert len(rendered.pages) >= 2

    artifacts = [
        descriptor(
            artifact_id="midi",
            artifact_type=ArtifactType.MIDI,
            filename="transcription-r7.mid",
            media_type=midi.artifact.media_type,
            extension=midi.artifact.file_extension,
            content=midi.artifact.content,
            order=0,
        ),
        descriptor(
            artifact_id="musicxml",
            artifact_type=ArtifactType.MUSICXML,
            filename="transcription-r7.musicxml",
            media_type=musicxml.artifact.media_type,
            extension=musicxml.artifact.file_extension,
            content=musicxml.artifact.content,
            order=1,
        ),
    ]
    artifacts.extend(
        descriptor(
            artifact_id=f"svg-page-{page.page_number:03d}",
            artifact_type=ArtifactType.SVG,
            filename=f"transcription-r7-page-{page.page_number:03d}.svg",
            media_type=page.media_type,
            extension=page.file_extension,
            content=page.content,
            order=index,
        )
        for index, page in enumerate(rendered.pages, start=2)
    )
    bundle = RevisionArtifactBundle(JOB_ID, 7, tuple(artifacts))
    repository = InMemoryRevisionArtifactRepository()
    jobs, revisions = existing_repositories()

    registered = RegisterRevisionArtifacts(jobs, revisions, repository).execute(bundle)

    assert registered is bundle
    midi_artifact = repository.get_artifact(JOB_ID, 7, "midi")
    musicxml_artifact = repository.get_artifact(JOB_ID, 7, "musicxml")
    assert midi_artifact is not None
    assert musicxml_artifact is not None
    assert midi_artifact.content == midi.artifact.content
    assert musicxml_artifact.content == musicxml.artifact.content
    for page in rendered.pages:
        stored = repository.get_artifact(JOB_ID, 7, f"svg-page-{page.page_number:03d}")
        assert stored is not None
        assert stored.content == page.content
