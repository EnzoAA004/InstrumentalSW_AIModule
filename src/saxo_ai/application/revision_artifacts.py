from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from saxo_ai.application.errors import (
    RevisionArtifactNotFoundError,
    RevisionArtifactsNotReadyError,
    RevisionNotFoundError,
    TranscriptionJobNotFoundError,
)
from saxo_ai.application.ports import (
    RevisionArtifactRepository,
    TranscriptionJobRepository,
    TranscriptionRevisionRepository,
)
from saxo_ai.domain.revision_artifacts import (
    RevisionArtifact,
    RevisionArtifactBundle,
    RevisionArtifactDescriptor,
    is_safe_artifact_id,
)


@dataclass(frozen=True, slots=True)
class RevisionArtifactListing:
    job_id: UUID
    revision_number: int
    artifacts: tuple[RevisionArtifactDescriptor, ...]


class RegisterRevisionArtifacts:
    def __init__(
        self,
        jobs: TranscriptionJobRepository,
        revisions: TranscriptionRevisionRepository,
        artifacts: RevisionArtifactRepository,
    ) -> None:
        self._jobs = jobs
        self._revisions = revisions
        self._artifacts = artifacts

    def execute(self, bundle: RevisionArtifactBundle) -> RevisionArtifactBundle:
        if not isinstance(bundle, RevisionArtifactBundle):
            raise TypeError("bundle must be RevisionArtifactBundle")
        _require_job_revision(
            bundle.job_id,
            bundle.revision_number,
            jobs=self._jobs,
            revisions=self._revisions,
        )
        return self._artifacts.save(bundle)


class ListRevisionArtifacts:
    def __init__(
        self,
        jobs: TranscriptionJobRepository,
        revisions: TranscriptionRevisionRepository,
        artifacts: RevisionArtifactRepository,
    ) -> None:
        self._jobs = jobs
        self._revisions = revisions
        self._artifacts = artifacts

    def execute(self, job_id: UUID, revision_number: int) -> RevisionArtifactListing:
        _require_job_revision(
            job_id,
            revision_number,
            jobs=self._jobs,
            revisions=self._revisions,
        )
        bundle = self._artifacts.get_bundle(job_id, revision_number)
        if bundle is None:
            raise RevisionArtifactsNotReadyError
        return RevisionArtifactListing(
            job_id=bundle.job_id,
            revision_number=bundle.revision_number,
            artifacts=tuple(value.descriptor for value in bundle.artifacts),
        )


class GetRevisionArtifact:
    def __init__(
        self,
        jobs: TranscriptionJobRepository,
        revisions: TranscriptionRevisionRepository,
        artifacts: RevisionArtifactRepository,
    ) -> None:
        self._jobs = jobs
        self._revisions = revisions
        self._artifacts = artifacts

    def execute(self, job_id: UUID, revision_number: int, artifact_id: str) -> RevisionArtifact:
        _require_job_revision(
            job_id,
            revision_number,
            jobs=self._jobs,
            revisions=self._revisions,
        )
        if self._artifacts.get_bundle(job_id, revision_number) is None:
            raise RevisionArtifactsNotReadyError
        if not is_safe_artifact_id(artifact_id):
            raise RevisionArtifactNotFoundError
        artifact = self._artifacts.get_artifact(job_id, revision_number, artifact_id)
        if artifact is None:
            raise RevisionArtifactNotFoundError
        return artifact


def _require_job_revision(
    job_id: UUID,
    revision_number: int,
    *,
    jobs: TranscriptionJobRepository,
    revisions: TranscriptionRevisionRepository,
) -> None:
    if jobs.get(job_id) is None:
        raise TranscriptionJobNotFoundError
    if revisions.get(job_id, revision_number) is None:
        raise RevisionNotFoundError
