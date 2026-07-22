from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest
from tests.review_helpers import JOB_ID, build_job, build_written_result

from saxo_ai.application.errors import (
    RevisionArtifactConflictError,
    RevisionArtifactNotFoundError,
    RevisionArtifactsNotReadyError,
    RevisionNotFoundError,
    TranscriptionJobNotFoundError,
)
from saxo_ai.application.revision_artifacts import (
    GetRevisionArtifact,
    ListRevisionArtifacts,
    RegisterRevisionArtifacts,
)
from saxo_ai.application.transcription_review import RegisterTranscriptionReview
from saxo_ai.domain.revision_artifacts import (
    ArtifactType,
    RevisionArtifact,
    RevisionArtifactBundle,
    RevisionArtifactDescriptor,
)
from saxo_ai.infrastructure.repositories import (
    InMemoryRevisionArtifactRepository,
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionReviewRegistrationRepository,
    InMemoryTranscriptionReviewRepository,
    InMemoryTranscriptionRevisionRepository,
)

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def bundle(content: bytes = b"MThd-real-bytes") -> RevisionArtifactBundle:
    descriptor = RevisionArtifactDescriptor(
        artifact_id="midi",
        artifact_type=ArtifactType.MIDI,
        filename="transcription-r0.mid",
        media_type="audio/midi",
        extension=".mid",
        size_bytes=len(content),
        sha256=sha256(content).hexdigest(),
        order=0,
    )
    return RevisionArtifactBundle(
        job_id=JOB_ID,
        revision_number=0,
        artifacts=(RevisionArtifact(descriptor, content),),
    )


def repositories() -> tuple[
    InMemoryTranscriptionJobRepository,
    InMemoryTranscriptionRevisionRepository,
    InMemoryRevisionArtifactRepository,
]:
    jobs = InMemoryTranscriptionJobRepository()
    reviews = InMemoryTranscriptionReviewRepository()
    revisions = InMemoryTranscriptionRevisionRepository()
    registration = InMemoryTranscriptionReviewRegistrationRepository(reviews, revisions)
    jobs.save(build_job())
    RegisterTranscriptionReview(jobs, registration, lambda: NOW).execute(JOB_ID, build_written_result())
    return jobs, revisions, InMemoryRevisionArtifactRepository()


def test_internal_registration_is_idempotent_for_exact_bundle_and_preserves_bytes() -> None:
    jobs, revisions, artifacts = repositories()
    use_case = RegisterRevisionArtifacts(jobs, revisions, artifacts)
    source = bundle()

    first = use_case.execute(source)
    second = use_case.execute(source)

    assert first is source
    assert second is source
    assert artifacts.get_bundle(JOB_ID, 0) is source
    assert artifacts.get_artifact(JOB_ID, 0, "midi") is source.artifacts[0]


def test_repository_rejects_incompatible_replacement_without_partial_change() -> None:
    jobs, revisions, artifacts = repositories()
    use_case = RegisterRevisionArtifacts(jobs, revisions, artifacts)
    original = bundle()
    use_case.execute(original)

    with pytest.raises(RevisionArtifactConflictError):
        use_case.execute(bundle(b"MThd-other-bytes"))

    assert artifacts.get_bundle(JOB_ID, 0) is original


def test_list_and_get_distinguish_unknown_job_revision_not_ready_and_missing_artifact() -> None:
    jobs, revisions, artifacts = repositories()
    list_artifacts = ListRevisionArtifacts(jobs, revisions, artifacts)
    get_artifact = GetRevisionArtifact(jobs, revisions, artifacts)

    missing_job = JOB_ID.__class__("22222222-2222-2222-2222-222222222222")
    with pytest.raises(TranscriptionJobNotFoundError):
        list_artifacts.execute(missing_job, 0)
    with pytest.raises(RevisionNotFoundError):
        list_artifacts.execute(JOB_ID, 99)
    with pytest.raises(RevisionArtifactsNotReadyError):
        list_artifacts.execute(JOB_ID, 0)

    RegisterRevisionArtifacts(jobs, revisions, artifacts).execute(bundle())
    with pytest.raises(RevisionArtifactNotFoundError):
        get_artifact.execute(JOB_ID, 0, "musicxml")


def test_list_returns_descriptors_only_and_get_returns_exact_registered_bytes() -> None:
    jobs, revisions, artifacts = repositories()
    source = bundle()
    RegisterRevisionArtifacts(jobs, revisions, artifacts).execute(source)

    listed = ListRevisionArtifacts(jobs, revisions, artifacts).execute(JOB_ID, 0)
    downloaded = GetRevisionArtifact(jobs, revisions, artifacts).execute(JOB_ID, 0, "midi")

    assert listed.job_id == JOB_ID
    assert listed.revision_number == 0
    assert listed.artifacts == (source.artifacts[0].descriptor,)
    assert not hasattr(listed.artifacts[0], "content")
    assert downloaded is source.artifacts[0]
    assert downloaded.content == b"MThd-real-bytes"
