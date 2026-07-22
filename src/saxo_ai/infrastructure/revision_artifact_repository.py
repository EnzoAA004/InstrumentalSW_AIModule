from __future__ import annotations

from threading import RLock
from uuid import UUID

from saxo_ai.application.errors import RevisionArtifactConflictError
from saxo_ai.domain.revision_artifacts import RevisionArtifact, RevisionArtifactBundle


class InMemoryRevisionArtifactRepository:
    def __init__(self) -> None:
        self._lock = RLock()
        self._bundles: dict[tuple[UUID, int], RevisionArtifactBundle] = {}

    def save(self, bundle: RevisionArtifactBundle) -> RevisionArtifactBundle:
        key = (bundle.job_id, bundle.revision_number)
        with self._lock:
            existing = self._bundles.get(key)
            if existing is not None:
                if existing is bundle or existing == bundle:
                    return existing
                raise RevisionArtifactConflictError
            self._bundles[key] = bundle
            return bundle

    def get_bundle(
        self, job_id: UUID, revision_number: int
    ) -> RevisionArtifactBundle | None:
        with self._lock:
            return self._bundles.get((job_id, revision_number))

    def get_artifact(
        self, job_id: UUID, revision_number: int, artifact_id: str
    ) -> RevisionArtifact | None:
        bundle = self.get_bundle(job_id, revision_number)
        if bundle is None:
            return None
        return next(
            (
                artifact
                for artifact in bundle.artifacts
                if artifact.descriptor.artifact_id == artifact_id
            ),
            None,
        )
